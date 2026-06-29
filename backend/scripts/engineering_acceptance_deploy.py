"""Deployment-related engineering acceptance checks."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_public_html_response_contract() -> None:
    for path in ("backend/app/routers/reports.py", "backend/app/routers/express.py"):
        text = _read(path)
        assert "_PUBLIC_HTML_HEADERS" in text, f"{path} 公开 HTML 必须设置统一响应头"
        assert '"Cache-Control": "no-store"' in text, f"{path} 公开 HTML 必须禁止缓存"
        assert '"X-Robots-Tag": "noindex, nofollow"' in text, f"{path} 公开 HTML 必须禁止搜索引擎索引"
        assert '"X-Content-Type-Options": "nosniff"' in text, f"{path} 公开 HTML 必须设置 nosniff"
        assert '"X-Frame-Options": "SAMEORIGIN"' in text, f"{path} 公开 HTML 必须限制跨站嵌入"
        assert "return _public_html_response(html)" in text, f"{path} 公开正文必须走统一 HTML 响应"


def check_container_deploy_contract() -> None:
    compose = _read("docker-compose.yml")
    backend_dockerfile = _read("backend/Dockerfile")
    backend_ignore = _read("backend/.dockerignore")
    frontend_dockerfile = _read("frontend/Dockerfile")
    frontend_ignore = _read("frontend/.dockerignore")
    nginx = _read("frontend/nginx.conf")
    config = _read("backend/app/config.py")
    assert "POSTGRES_PASSWORD:?set POSTGRES_PASSWORD" in compose, "Compose 不能给数据库密码设置弱默认值"
    assert "JWT_SECRET_KEY:?set JWT_SECRET_KEY" in compose, "Compose 必须要求显式 JWT 密钥"
    assert "SECRET_ENCRYPTION_KEY:?set SECRET_ENCRYPTION_KEY" in compose, "Compose 必须要求显式运行时密钥加密材料"
    assert "ADMIN_PASSWORD:?set ADMIN_PASSWORD" in compose, "Compose 必须要求显式初始管理员密码"
    assert "UPLOAD_API_KEY:?set UPLOAD_API_KEY" in compose, "Compose 必须要求显式上传 API Key"
    assert "pg_isready -U ${POSTGRES_USER:-market} -d ${POSTGRES_DB:-market}" in compose, "数据库健康检查必须使用实际配置的库名和用户名"
    assert "/api/ready" in compose, "后端容器健康检查必须使用 readiness"
    assert "condition: service_healthy" in compose, "前端不能在后端未就绪时接流量"
    assert "mcr.microsoft.com/playwright/python:v1.60.0-noble" in backend_dockerfile, "后端镜像 Playwright 版本必须与 requirements 对齐"
    assert "apt-get install -y --no-install-recommends curl" in backend_dockerfile, "后端镜像必须包含采集 HTTP 兜底所需 curl"
    assert "assert_production_security" in backend_dockerfile, "后端镜像迁移前必须先校验生产密钥"
    assert "assert_production_security()' && python -m alembic upgrade head" in backend_dockerfile, "后端镜像必须先校验配置再执行迁移"
    for marker in ("market.db", ".env", "output/", "cookies/"):
        assert marker in backend_ignore, f"后端镜像构建必须排除 {marker}"
    assert "RUN npm ci" in frontend_dockerfile, "前端镜像构建必须使用 lockfile 确定性安装"
    for marker in ("node_modules", "dist", ".env"):
        assert marker in frontend_ignore, f"前端镜像构建必须排除 {marker}"
    assert "proxy_read_timeout 300s" in nginx, "前端反向代理超时必须覆盖长任务"
    assert "location /r/" in nginx and "proxy_pass http://backend:8000/r/" in nginx, "生产 Nginx 必须代理报告分享链接"
    assert "location /re/" in nginx and "proxy_pass http://backend:8000/re/" in nginx, "生产 Nginx 必须代理速递分享链接"
    assert "X-Content-Type-Options" in nginx and "X-Frame-Options" in nginx, "Nginx 必须设置基础安全响应头"
    assert "def assert_production_security" in config, "后端生产模式必须启动前拦截弱密钥"
    assert "Production deployment requires strong explicit secrets" in config, "弱密钥错误必须清晰"

    compose_config = subprocess.run(
        ["docker", "compose", "--env-file", ".env.example", "config"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert compose_config.returncode == 0, compose_config.stderr
    assert "condition: service_healthy" in compose_config.stdout, "Compose 解析后必须保留健康依赖"

    script = "from app.config import assert_production_security; assert_production_security()"
    base_env = os.environ.copy()
    base_env.update({
        "DATABASE_URL": "postgresql+asyncpg://market:secret@db:5432/market",
        "JWT_SECRET_KEY": "change-me-in-production",
        "SECRET_ENCRYPTION_KEY": "replace-with-at-least-32-random-characters",
        "ADMIN_PASSWORD": "admin123",
        "UPLOAD_API_KEY": "change-me-in-production",
    })
    weak = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        env=base_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert weak.returncode != 0 and "Production deployment requires strong explicit secrets" in weak.stderr

    strong_env = base_env.copy()
    strong_env.update({
        "JWT_SECRET_KEY": "j" * 40,
        "SECRET_ENCRYPTION_KEY": "s" * 40,
        "ADMIN_PASSWORD": "StrongAdminPassword2026!",
        "UPLOAD_API_KEY": "u" * 40,
    })
    strong = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        env=strong_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert strong.returncode == 0, strong.stderr


def _write_public_env(path: Path, *, secure_cookie: bool = True) -> None:
    secure = "true" if secure_cookie else "false"
    path.write_text(
        "\n".join([
            "COMPOSE_PROJECT_NAME=market-product",
            "MARKET_DOMAIN=market.acme-corp.cn",
            "ACME_EMAIL=ops@acme-corp.cn",
            "POSTGRES_DB=market",
            "POSTGRES_USER=market",
            "POSTGRES_PASSWORD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "DATABASE_SCHEMA=marketing",
            "JWT_SECRET_KEY=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "SECRET_ENCRYPTION_KEY=cccccccccccccccccccccccccccccccccccccccc",
            "ADMIN_USERNAME=admin",
            "ADMIN_PASSWORD=dddddddddddddddddddddddddddddddddddddddd",
            "UPLOAD_API_KEY=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "AUTH_COOKIE_NAME=market_session",
            f"AUTH_COOKIE_SECURE={secure}",
            "AUTH_COOKIE_SAMESITE=strict",
            'CORS_ORIGINS=["https://market.acme-corp.cn"]',
            "",
        ]),
        encoding="utf-8",
    )


def check_public_deployment_toolkit_contract() -> None:
    prod_compose = _read("deploy/docker-compose.prod.yml")
    caddyfile = _read("deploy/Caddyfile")
    root_install = _read("install.sh")
    install = _read("deploy/install.sh")
    update = _read("deploy/update.sh")
    marketctl = _read("deploy/marketctl.sh")
    prod_env = _read("deploy/env.production.example")
    smoke = _read("backend/scripts/deployment_smoke.py")
    frontend_dockerignore = _read("frontend/.dockerignore")
    gate = _read("backend/scripts/security_quality_gate.py")

    assert "gateway:" in prod_compose and '\"80:80\"' in prod_compose and '\"443:443\"' in prod_compose, "生产部署必须只有公网网关入口"
    for service in ("db", "backend", "frontend"):
        block_start = prod_compose.index(f"  {service}:")
        next_match = prod_compose.find("\n  ", block_start + 3)
        block = prod_compose[block_start:] if next_match == -1 else prod_compose[block_start:next_match]
        assert "\n    ports:" not in block, f"生产部署中 {service} 不得发布宿主机端口"
    assert "internal: true" in prod_compose, "生产部署必须使用 Docker internal 网络隔离后端与数据库"
    assert "AUTH_COOKIE_SECURE: ${AUTH_COOKIE_SECURE:-true}" in prod_compose, "生产部署必须默认 Secure Cookie"
    assert "Strict-Transport-Security" in caddyfile and "reverse_proxy frontend:80" in caddyfile, "公网网关必须有 TLS 安全头和前端代理"
    for command in ("init", "doctor", "gate", "up", "smoke", "update", "backup", "restore", "pack"):
        assert f"{command})" in marketctl or f"cmd_{command}" in marketctl, f"部署工具缺少 {command} 命令"
    assert "seed-snapshot)" in marketctl and "cmd_seed_snapshot" in marketctl, "部署工具必须提供快照导入命令"
    assert "cmd_backup" in marketctl and "compose up -d --build --remove-orphans" in marketctl, "更新必须先备份再一键替换"
    assert "cmd_smoke" in marketctl and "deployment_smoke.py" in marketctl, "部署工具必须提供上线冒烟"
    assert "宿主机未安装 npm" in marketctl, "服务器部署不能强依赖宿主机 Node.js"
    for excluded in (
        "frontend/src/.umi",
        "frontend/src/.umi-production",
        "__pycache__",
        "*.pyc",
        "*.db",
        "*.db-shm",
        "*.db-wal",
        "*.log",
        ".DS_Store",
    ):
        assert f"--exclude='{excluded}'" in marketctl, f"部署包必须排除本机构建/缓存产物：{excluded}"
    for excluded in ("src/.umi", "src/.umi-production", ".umi", ".umi-production"):
        assert excluded in frontend_dockerignore, f"前端 Docker 上下文必须排除生成目录：{excluded}"
    assert "MARKET_DOMAIN=market.example.com" in prod_env and "AUTH_COOKIE_SECURE=true" in prod_env, "生产 env 示例必须面向 HTTPS 公网"
    assert "SECURITY GATE PASSED" in gate and "真实公网域名" in gate and "AUTH_COOKIE_SECURE=true" in gate, "安全门禁必须检查公网域名与 Cookie 策略"
    assert "--domain" in marketctl and "--email" in marketctl and "security_quality_gate.py" in marketctl, "初始化 .env 必须要求域名邮箱并自动跑门禁"
    assert 'deploy/install.sh" "$@"' in root_install, "根目录必须提供小白一键部署入口"
    for marker in ("docker compose version", "marketctl.sh", "doctor", "init --domain", "up", "seed-snapshot", "smoke", "ADMIN_PASSWORD"):
        assert marker in install, f"一键部署脚本缺少关键步骤：{marker}"
    assert 'marketctl.sh" update' in update and "自动备份数据库" in update, "一键更新脚本必须调用受控更新流程"
    for marker in ("/api/ready", "/api/auth/login", "/api/settings/system", "/api/crawlers/status", "/api/aipaas-sync/config"):
        assert marker in smoke, f"上线冒烟脚本缺少核心接口检查：{marker}"

    with tempfile.NamedTemporaryFile("w", delete=False) as ok_env:
        ok_path = Path(ok_env.name)
    with tempfile.NamedTemporaryFile("w", delete=False) as bad_env:
        bad_path = Path(bad_env.name)
    try:
        _write_public_env(ok_path, secure_cookie=True)
        ok = subprocess.run(
            [sys.executable, "backend/scripts/security_quality_gate.py", "--env", str(ok_path), "--profile", "public"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert ok.returncode == 0, ok.stdout + ok.stderr

        compose_config = subprocess.run(
            ["docker", "compose", "--env-file", str(ok_path), "-f", "deploy/docker-compose.prod.yml", "config"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert compose_config.returncode == 0, compose_config.stderr
        assert 'published: "443"' in compose_config.stdout and 'published: "80"' in compose_config.stdout, "公网部署必须发布 80/443"
        assert 'published: "5432"' not in compose_config.stdout and 'published: "8000"' not in compose_config.stdout, "公网部署不得发布数据库或后端端口"

        _write_public_env(bad_path, secure_cookie=False)
        bad = subprocess.run(
            [sys.executable, "backend/scripts/security_quality_gate.py", "--env", str(bad_path), "--profile", "public"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert bad.returncode != 0 and "AUTH_COOKIE_SECURE=true" in bad.stdout, "安全门禁必须拦截公网非 Secure Cookie"
    finally:
        for path in (ok_path, bad_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

