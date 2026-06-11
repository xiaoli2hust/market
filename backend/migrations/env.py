"""Alembic 迁移环境。

将运行时使用的 ``postgresql+asyncpg://`` 连接串改写为同步
``postgresql+psycopg2://``，因为 Alembic 不支持异步引擎。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---- 让 ``app`` 包可导入 -------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from app.database import Base  # noqa: E402  pylint: disable=wrong-import-position
from app import models  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_sync_url() -> str:
    """从环境变量或配置中读取 URL，并替换为同步 psycopg2 驱动。"""

    raw = (
        os.getenv("ALEMBIC_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or settings.DATABASE_URL
    )
    if not raw:
        raise RuntimeError("DATABASE_URL is not configured for Alembic")
    return (
        raw.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgres+asyncpg://", "postgresql+psycopg2://")
    )


SYNC_URL = _resolve_sync_url()
config.set_main_option("sqlalchemy.url", SYNC_URL)

target_metadata = Base.metadata
TARGET_SCHEMA = settings.DATABASE_SCHEMA or None


def _include_object(object_, name, type_, reflected, compare_to):  # noqa: ARG001
    """忽略其他 schema 的对象，避免误改公共表。"""

    if type_ == "table" and TARGET_SCHEMA:
        schema = getattr(object_, "schema", None)
        if schema is not None and schema != TARGET_SCHEMA:
            return False
    return True


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接数据库。"""

    context.configure(
        url=SYNC_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=TARGET_SCHEMA,
        include_schemas=True,
        include_object=_include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：通过同步引擎实际执行迁移。"""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        if TARGET_SCHEMA:
            connection.exec_driver_sql(
                f'CREATE SCHEMA IF NOT EXISTS "{TARGET_SCHEMA}"'
            )
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=TARGET_SCHEMA,
            include_schemas=True,
            include_object=_include_object,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
