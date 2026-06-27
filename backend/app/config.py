"""应用配置管理。

通过 pydantic-settings 加载环境变量，支持 .env 文件覆盖。
所有运行时可调参数集中在此处，避免在业务代码中硬编码。
"""

from __future__ import annotations

import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """全局配置项。"""

    # Database
    # 默认使用 SQLite 便于本机零依赖启动；如需 PostgreSQL，请在 .env 中覆盖。
    DATABASE_URL: str = "sqlite+aiosqlite:///./market.db"
    DATABASE_SCHEMA: str = "marketing"

    # LLM (DeepSeek OpenAI 兼容接口)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # DingTalk
    DINGTALK_WEBHOOK_URL: str = ""
    DINGTALK_SECRET: str = ""

    # AIPAAS 日报拉取
    AIPAAS_BASE_URL: str = ""
    AIPAAS_APP_ID: str = ""
    AIPAAS_SYNC_ENABLED: bool = False
    AIPAAS_SYNC_INTERVAL_MINUTES: int = 60

    # 结构化标讯
    JIANYU_USERNAME: str = ""
    JIANYU_PASSWORD: str = ""

    # Auth
    JWT_SECRET_KEY: str = ""
    SECRET_ENCRYPTION_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    AUTH_COOKIE_NAME: str = "market_session"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "strict"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    # Upload API Key (内网上传认证)
    UPLOAD_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://localhost:8002",
    ]
    ENABLE_LOCAL_PREVIEW: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


# ---------------------------------------------------------------------------
# 开发模式安全兜底：当环境变量未设置时自动生成随机值，避免使用硬编码弱凭证。
# ---------------------------------------------------------------------------
_DEV_WEAK_VALUES = {
    "",
    "admin123",
    "change-me",
    "change-me-in-production",
    "please-change-me",
    "dev-only-change-me-in-production-32-byte-minimum",
    "dev-upload-key",
}

def _is_weak(value: str, min_length: int = 0) -> bool:
    """检查凭证值是否过于简单（在弱值列表中或长度不足）。"""
    clean = (value or "").strip()
    if clean in _DEV_WEAK_VALUES:
        return True
    if min_length and len(clean) < min_length:
        return True
    return False

if _is_weak(settings.JWT_SECRET_KEY, min_length=32):
    settings.JWT_SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning(
        "⚠️  未设置 JWT_SECRET_KEY，已使用随机开发值。生产环境请通过环境变量配置。"
    )

if _is_weak(settings.ADMIN_PASSWORD, min_length=12):
    settings.ADMIN_PASSWORD = secrets.token_urlsafe(16)
    logger.warning(
        "⚠️  未设置 ADMIN_PASSWORD，已使用随机开发值。生产环境请通过环境变量配置。"
    )

if _is_weak(settings.UPLOAD_API_KEY, min_length=32):
    settings.UPLOAD_API_KEY = secrets.token_urlsafe(32)
    logger.warning(
        "⚠️  未设置 UPLOAD_API_KEY，已使用随机开发值。生产环境请通过环境变量配置。"
    )


def is_sqlite_database(url: str | None = None) -> bool:
    """Return whether the configured database is local SQLite."""

    return (url or settings.DATABASE_URL).lower().startswith("sqlite")


def assert_production_security() -> None:
    """Fail fast when production-like deployments still use placeholder secrets."""

    if is_sqlite_database():
        logger.warning("SQLite 模式跳过安全强度检查 — 仅限本地开发使用")
        return

    weak_values = {
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
    }
    checks = {
        "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
        "SECRET_ENCRYPTION_KEY": settings.SECRET_ENCRYPTION_KEY,
        "ADMIN_PASSWORD": settings.ADMIN_PASSWORD,
        "UPLOAD_API_KEY": settings.UPLOAD_API_KEY,
    }
    problems = []
    for name, value in checks.items():
        normalized = (value or "").strip()
        if normalized in weak_values:
            problems.append(name)
            continue
        if name in {"JWT_SECRET_KEY", "SECRET_ENCRYPTION_KEY", "UPLOAD_API_KEY"} and len(normalized) < 32:
            problems.append(name)
        if name == "ADMIN_PASSWORD" and len(normalized) < 12:
            problems.append(name)
    if problems:
        raise RuntimeError(
            "Production deployment requires strong explicit secrets: "
            + ", ".join(sorted(set(problems)))
        )
