"""FastAPI 应用入口。

负责装配 lifespan、CORS、路由聚合与健康检查。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .config import assert_production_security, settings
from .database import dispose_db, engine, init_db
from .routers import api_router
from .routers.reports import public_router as report_public_router
from .routers.express import public_router as express_public_router
from .schemas import HealthResponse
from .services.crawler_scheduler import start_crawler_scheduler, stop_crawler_scheduler
from .sqlite_auto_migration import _auto_migrate_sqlite

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
    assert_production_security()
    # 本机 SQLite 开发模式下自动创建缺失表，便于零配置试用。
    if settings.DATABASE_URL.lower().startswith("sqlite"):
        await init_db()
    # 自动迁移：为已有 SQLite 表添加新增的列（安全操作，已有列会跳过）
    _auto_migrate_sqlite()
    start_crawler_scheduler()
    try:
        yield
    finally:
        await stop_crawler_scheduler()
        await dispose_db()
        logger.info("marketing backend stopped")




app = FastAPI(
    title="Market 数据采集中心 API",
    description="面向部门日报周报、市场洞察研判、商机推进预测与系统管理的后端服务。",
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


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF 防护：状态修改请求必须携带 JSON Content-Type 或自定义头部。

    原理：浏览器自动附加 Cookie 的跨站请求无法设置 Content-Type: application/json
    或自定义 X-Requested-With 头部，因此可以阻断 CSRF 攻击。
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            content_type = request.headers.get("content-type", "")
            has_json = "application/json" in content_type
            has_custom_header = "x-requested-with" in request.headers
            if not has_json and not has_custom_header:
                return JSONResponse(
                    {"detail": "CSRF check failed: 请求必须包含 Content-Type: application/json 或 X-Requested-With 头部"},
                    status_code=403,
                )
        return await call_next(request)


app.add_middleware(CSRFProtectionMiddleware)

app.include_router(api_router, prefix="/api")

# 公开分享链接：/r/{token} 和 /re/{token}，不带 /api 前缀、不需要 JWT 认证
app.include_router(report_public_router)
app.include_router(express_public_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """根路径指向 API 文档；正式产品入口由前端服务提供。"""

    return RedirectResponse(url="/api/docs")


@app.get("/preview", include_in_schema=False)
async def preview_page() -> FileResponse:
    """内置的零依赖看板预览页，直接调用 /api/* 渲染活动数据。"""

    if not settings.ENABLE_LOCAL_PREVIEW:
        raise HTTPException(status_code=404, detail="local preview is disabled")
    return FileResponse(STATIC_DIR / "preview.html", media_type="text/html")


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness：进程存活即可返回。"""

    return HealthResponse(status="ok", version=__version__)


@app.get("/api/ready", response_model=HealthResponse, tags=["system"])
async def readiness() -> HealthResponse:
    """Readiness：确认数据库可连接，供容器编排决定是否接流量。"""

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("readiness check failed")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthResponse(status="ready", version=__version__)
