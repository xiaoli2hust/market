"""应用配置管理。

通过 pydantic-settings 加载环境变量，支持 .env 文件覆盖。
所有运行时可调参数集中在此处，避免在业务代码中硬编码。
"""

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

    # 剑鱼标讯
    JIANYU_USERNAME: str = ""
    JIANYU_PASSWORD: str = ""

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
