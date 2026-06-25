"""Security quality gate for public-facing Market deployments.

This script intentionally uses only the Python standard library so it can run
before project dependencies are installed. It checks deployment configuration
and source contracts that must hold before exposing the platform to the
internet.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

WEAK_VALUES = {
    "",
    "admin123",
    "change-me",
    "change-me-in-production",
    "please-change-me",
    "replace-with-a-strong-db-password",
    "replace-with-a-strong-initial-password",
    "replace-with-a-strong-upload-key",
    "replace-with-at-least-32-random-characters",
    "dev-only-change-me-in-production-32-byte-minimum",
    "market.example.com",
    "market.example.cn",
    "ops@example.com",
    "ops@example.cn",
}

SECRET_FIELDS = {
    "POSTGRES_PASSWORD": 24,
    "JWT_SECRET_KEY": 32,
    "SECRET_ENCRYPTION_KEY": 32,
    "ADMIN_PASSWORD": 12,
    "UPLOAD_API_KEY": 32,
}


class GateFailure(Exception):
    pass


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise GateFailure(f"环境文件不存在: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _service_block(compose: str, service_name: str) -> str:
    match = re.search(rf"^  {re.escape(service_name)}:\n(?P<body>(?:    .*\n|      .*\n|        .*\n|          .*\n)*)", compose, re.MULTILINE)
    if not match:
        raise GateFailure(f"生产 compose 缺少服务: {service_name}")
    return match.group("body")


def _assert(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _looks_like_real_public_domain(domain: str) -> bool:
    value = (domain or "").strip().lower().strip(".")
    if not value or value in WEAK_VALUES:
        return False
    if value.startswith(("http://", "https://")):
        return False
    if any(marker in value for marker in ("localhost", "example", "your-domain", "yourdomain")):
        return False
    if value.endswith((".local", ".invalid", ".test", ".localhost")):
        return False
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        pass
    return bool(re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value))


def _looks_like_real_email(email: str) -> bool:
    value = (email or "").strip().lower()
    if not value or value in WEAK_VALUES:
        return False
    if any(marker in value for marker in ("example", "your-email", "yourdomain")):
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def check_env(env: dict[str, str], profile: str, failures: list[str]) -> None:
    for field, min_length in SECRET_FIELDS.items():
        value = env.get(field, "")
        _assert(value not in WEAK_VALUES, f"{field} 不能使用占位值或弱默认值", failures)
        _assert(len(value) >= min_length, f"{field} 长度不足，至少 {min_length} 位", failures)

    domain = env.get("MARKET_DOMAIN", "")
    _assert(_looks_like_real_public_domain(domain), "MARKET_DOMAIN 必须配置为真实公网域名，不能使用示例域名、localhost、IP 或 .local/.test/.invalid", failures)
    _assert(not domain.startswith("http://") and not domain.startswith("https://"), "MARKET_DOMAIN 只填写域名，不要带协议", failures)
    if profile == "public":
        _assert(_looks_like_real_email(env.get("ACME_EMAIL", "")), "ACME_EMAIL 必须配置为真实证书通知邮箱，不能使用示例邮箱", failures)

    if profile == "public":
        _assert(env.get("AUTH_COOKIE_SECURE", "").lower() == "true", "公网 HTTPS 部署必须启用 AUTH_COOKIE_SECURE=true", failures)
        _assert(env.get("AUTH_COOKIE_SAMESITE", "").lower() in {"strict", "lax"}, "AUTH_COOKIE_SAMESITE 必须是 strict 或 lax", failures)
        _assert("localhost" not in domain and "127.0.0.1" not in domain, "公网部署域名不能是 localhost/127.0.0.1", failures)

    cors_raw = env.get("CORS_ORIGINS", "")
    try:
        cors = json.loads(cors_raw)
    except json.JSONDecodeError:
        cors = []
        failures.append("CORS_ORIGINS 必须是 JSON 数组")
    _assert(isinstance(cors, list) and cors, "CORS_ORIGINS 必须至少包含一个来源", failures)
    _assert("*" not in cors, "CORS_ORIGINS 不能使用 *", failures)
    if domain and profile == "public":
        _assert(f"https://{domain}" in cors, "CORS_ORIGINS 必须包含公网 HTTPS 域名", failures)
        _assert(all(str(item).startswith("https://") for item in cors), "公网部署 CORS 只允许 HTTPS 来源", failures)


def check_public_compose(failures: list[str]) -> None:
    compose = _read("deploy/docker-compose.prod.yml")
    for service in ("db", "backend", "frontend"):
        block = _service_block(compose, service)
        _assert("\n    ports:" not in block, f"{service} 不能发布宿主机端口", failures)
    gateway = _service_block(compose, "gateway")
    _assert('"80:80"' in gateway and '"443:443"' in gateway, "公网入口只能由 gateway 发布 80/443", failures)
    _assert("internal: true" in compose, "后端和数据库网络必须是 internal", failures)
    _assert("AUTH_COOKIE_SECURE: ${AUTH_COOKIE_SECURE:-true}" in compose, "生产 compose 必须默认启用 Secure Cookie", failures)
    _assert("ENABLE_LOCAL_PREVIEW: \"false\"" in compose, "生产 compose 必须关闭本地预览页", failures)
    _assert("condition: service_healthy" in compose, "生产 compose 必须按健康检查编排启动顺序", failures)


def check_gateway(failures: list[str]) -> None:
    caddy = _read("deploy/Caddyfile")
    for marker in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Permissions-Policy",
        "reverse_proxy frontend:80",
    ):
        _assert(marker in caddy, f"Caddyfile 缺少安全/代理配置: {marker}", failures)


def check_source_contracts(failures: list[str]) -> None:
    backend_dockerfile = _read("backend/Dockerfile")
    frontend_dockerfile = _read("frontend/Dockerfile")
    frontend_nginx = _read("frontend/nginx.conf")
    config = _read("backend/app/config.py")
    auth_router = _read("backend/app/routers/auth.py")
    auth_dep = _read("backend/app/auth.py")

    _assert("assert_production_security()' && python -m alembic upgrade head" in backend_dockerfile, "后端容器必须先校验生产密钥再迁移", failures)
    _assert("RUN npm ci" in frontend_dockerfile, "前端容器构建必须使用 npm ci", failures)
    _assert("allow_credentials=True" in _read("backend/app/main.py"), "后端 CORS 必须允许 Cookie 凭证", failures)
    _assert("response.set_cookie" in auth_router and "httponly=True" in auth_router, "登录必须写入 HttpOnly Cookie", failures)
    _assert("HTTP_429_TOO_MANY_REQUESTS" in auth_router, "登录失败必须有限流保护", failures)
    _assert("Cookie(default=None" in auth_dep, "鉴权依赖必须支持 HttpOnly Cookie", failures)
    _assert("def assert_production_security" in config, "后端必须具备生产密钥启动前校验", failures)
    for marker in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "location /api/", "location /r/", "location /re/"):
        _assert(marker in frontend_nginx, f"前端 Nginx 缺少 {marker}", failures)


def check_secret_leaks(failures: list[str]) -> None:
    # Keep this denylist generic. Never place a real customer account, phone
    # number, API key, or password here; the checker itself is committed code.
    forbidden = (
        "POSTGRES_PASSWORD=pass",
        "postgresql://user:pass",
        "DINGTALK_SECRET=xxx",
        "QWEN_API_KEY=xxx",
        "UPLOAD_API_KEY=xxx",
        "access_token=xxx",
    )
    suspicious_patterns = (
        ("mainland phone number", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
        ("DingTalk client id", re.compile(r"\bding[a-z0-9]{12,}\b", re.IGNORECASE)),
        ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    )
    allowed_dirs = {"node_modules", "dist", ".git", ".runtime"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if path == Path(__file__).resolve():
            continue
        if any(part in allowed_dirs for part in rel.parts):
            continue
        if path.suffix in {".pyc", ".db", ".sqlite", ".png", ".jpg", ".jpeg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in forbidden:
            if marker in text:
                failures.append(f"疑似敏感信息残留: {rel} 包含 {marker}")
        for label, pattern in suspicious_patterns:
            if pattern.search(text):
                failures.append(f"疑似敏感信息残留: {rel} 命中 {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Market public deployment security gate.")
    parser.add_argument("--env", default=".env", help="env file path, relative to repo root by default")
    parser.add_argument("--profile", choices=["public", "internal"], default="public")
    args = parser.parse_args()

    env_path = Path(args.env)
    if not env_path.is_absolute():
        env_path = ROOT / env_path

    failures: list[str] = []
    try:
        env = _parse_env(env_path)
        check_env(env, args.profile, failures)
        check_public_compose(failures)
        check_gateway(failures)
        check_source_contracts(failures)
        check_secret_leaks(failures)
    except GateFailure as exc:
        failures.append(str(exc))

    if failures:
        print("SECURITY GATE FAILED")
        for item in failures:
            print(f"- {item}")
        return 1

    print("SECURITY GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
