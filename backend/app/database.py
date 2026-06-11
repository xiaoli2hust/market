"""数据库连接与会话管理。

支持两种模式：
- ``sqlite+aiosqlite``：本机零依赖开发模式（默认）。不创建 schema、不切 search_path。
- ``postgresql+asyncpg``：生产模式。所有业务表归属 ``settings.DATABASE_SCHEMA``。

FastAPI 路由通过 ``get_db`` 依赖注入获取 ``AsyncSession``。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


def _is_sqlite(url: str) -> bool:
    """判断当前是否运行在 SQLite 模式。"""

    return url.lower().startswith("sqlite")


# SQLite 模式下不使用 schema，避免 ``marketing.staff`` 形式的限定名导致建表失败。
_USE_SCHEMA = bool(settings.DATABASE_SCHEMA) and not _is_sqlite(settings.DATABASE_URL)


class Base(DeclarativeBase):
    """全局 ORM 基类。所有模型继承自此。

    在 PostgreSQL 模式下会注入带 schema 的 MetaData；在 SQLite 模式下保持默认 schema=None，
    保证两种数据库都能用同一份模型定义建表。
    """

    metadata = MetaData(schema=settings.DATABASE_SCHEMA if _USE_SCHEMA else None)


def _build_engine_kwargs() -> dict:
    """根据数据库类型组装 ``create_async_engine`` 参数。"""

    if _is_sqlite(settings.DATABASE_URL):
        # SQLite 不需要连接池预检和回收，使用默认 NullPool 行为更稳定。
        return {"echo": False, "future": True}
    return {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "future": True,
    }


# 异步引擎：根据 DSN 协议自动选择驱动行为。
engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())


if _USE_SCHEMA:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):  # pragma: no cover
        """PostgreSQL 连接建立后，将 search_path 切换到目标 schema。"""

        schema = settings.DATABASE_SCHEMA
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{schema}", public')
        finally:
            cursor.close()


SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 兼容旧脚本的别名。新代码请使用 ``SessionLocal``。
async_session = SessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供一个事务化的异步 Session。"""

    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """开发期辅助：基于模型定义创建表（生产请走 Alembic 迁移）。

    SQLite 模式下直接 ``create_all``；PostgreSQL 模式下先确保 schema 存在。
    """

    # 延迟导入，避免循环引用；models 注册到 Base.metadata。
    from . import models  # noqa: F401  pylint: disable=unused-import

    async with engine.begin() as conn:
        if _USE_SCHEMA:
            await conn.exec_driver_sql(
                f'CREATE SCHEMA IF NOT EXISTS "{settings.DATABASE_SCHEMA}"'
            )
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """应用退出时优雅关闭引擎连接池。"""

    await engine.dispose()
