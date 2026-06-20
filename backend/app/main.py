"""FastAPI 应用入口。

负责装配 lifespan、CORS、路由聚合与健康检查。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import __version__
from .config import settings
from .database import dispose_db
from .routers import api_router
from .routers.reports import public_router as report_public_router
from .routers.express import public_router as express_public_router
from .schemas import HealthResponse

logger = logging.getLogger(__name__)

# 静态预览页路径：本机零依赖预览看板（无需 Node）。
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """应用生命周期：启动时记录配置，退出时释放数据库连接池。"""

    logger.info(
        "starting marketing backend",
        extra={"schema": settings.DATABASE_SCHEMA, "model": settings.LLM_MODEL},
    )
    # 自动迁移：为已有 SQLite 表添加新增的列（安全操作，已有列会跳过）
    _auto_migrate_sqlite()
    try:
        yield
    finally:
        await dispose_db()
        logger.info("marketing backend stopped")


def _auto_migrate_sqlite() -> None:
    """SQLite 不会自动 ALTER TABLE，启动时补建缺失列。"""
    if not settings.DATABASE_URL.lower().startswith("sqlite"):
        return
    try:
        import sqlite3
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("./", "")
        conn = sqlite3.connect(db_path)
        # DingtalkConfig: 新增 app_key, app_secret 列
        cols = [row[1] for row in conn.execute("PRAGMA table_info(dingtalk_configs)").fetchall()]
        if cols and "app_key" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN app_key VARCHAR(255)")
        if cols and "app_secret" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN app_secret VARCHAR(255)")
        if cols and "jianyu_username" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN jianyu_username VARCHAR(100)")
        if cols and "jianyu_password" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN jianyu_password VARCHAR(255)")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("SQLite auto-migrate skipped: %s", e)


app = FastAPI(
    title="营销数据驾驶舱 API",
    description="对接钉钉机器人、LLM 与营销数据采集的后端服务。",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# 公开分享链接：/r/{token} 和 /re/{id}，不带 /api 前缀、不需要 JWT 认证
app.include_router(report_public_router)
app.include_router(express_public_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """根路径重定向到静态预览页，方便本机使用者直接访问首页。"""

    return RedirectResponse(url="/preview")


@app.get("/preview", include_in_schema=False)
async def preview_page() -> FileResponse:
    """内置的零依赖看板预览页，直接调用 /api/* 渲染活动数据。"""

    return FileResponse(STATIC_DIR / "preview.html", media_type="text/html")


@app.get("/bidding-demo", include_in_schema=False)
async def bidding_express_demo() -> FileResponse:
    """标讯速递 Demo 预览页。"""
    demo_path = STATIC_DIR / "bidding_express_demo.html"
    if demo_path.exists():
        return FileResponse(demo_path, media_type="text/html")
    return FileResponse(STATIC_DIR / "preview.html", media_type="text/html")


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """健康检查。"""

    return HealthResponse(status="ok", version=__version__)
