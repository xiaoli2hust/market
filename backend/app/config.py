"""应用配置管理。

通过 pydantic-settings 加载环境变量，支持 .env 文件覆盖。
所有运行时可调参数集中在此处，避免在业务代码中硬编码。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # 结构化标讯
    JIANYU_USERNAME: str = ""
    JIANYU_PASSWORD: str = ""

    # Auth
    JWT_SECRET_KEY: str = "dev-only-change-me-in-production-32-byte-minimum"
    SECRET_ENCRYPTION_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    AUTH_COOKIE_NAME: str = "market_session"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "strict"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # Upload API Key (内网上传认证)
    UPLOAD_API_KEY: str = "change-me-in-production"

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


def is_sqlite_database(url: str | None = None) -> bool:
    """Return whether the configured database is local SQLite."""

    return (url or settings.DATABASE_URL).lower().startswith("sqlite")


def assert_production_security() -> None:
    """Fail fast when production-like deployments still use placeholder secrets."""

    if is_sqlite_database():
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
