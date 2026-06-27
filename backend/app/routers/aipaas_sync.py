"""AIPAAS 日报同步管理路由。

提供手动触发拉取、配置查看、用户列表管理等接口。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..config import settings
from ..database import get_db
from ..services.aipaas_service import pull_aipaas_daily_reports

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aipaas-sync", tags=["aipaas-sync"])


# ---------- 请求/响应模型 ----------


class AipaasUserItem(BaseModel):
    user_id: str = Field(..., description="工号")
    user_name: str = Field(..., description="姓名")


class AipaasSyncTriggerRequest(BaseModel):
    date: str | None = Field(default=None, description="拉取日期 YYYY-MM-DD，默认今天")
    users: list[AipaasUserItem] = Field(default_factory=list, description="用户列表")

    model_config = {"str_strip_whitespace": True}


class AipaasConfigUpdateRequest(BaseModel):
    base_url: str | None = None
    app_id: str | None = None
    sync_enabled: bool | None = None
    sync_interval_minutes: int | None = None


# ---------- 接口 ----------


@router.get("/config")
async def get_config(
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """查看 AIPAAS 同步配置。"""
    return {
        "base_url": settings.AIPAAS_BASE_URL,
        "app_id": settings.AIPAAS_APP_ID,
        "sync_enabled": settings.AIPAAS_SYNC_ENABLED,
        "sync_interval_minutes": settings.AIPAAS_SYNC_INTERVAL_MINUTES,
    }


@router.put("/config")
async def update_config(
    payload: AipaasConfigUpdateRequest,
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """更新 AIPAAS 同步配置（运行时生效，重启后需 .env 持久化）。"""
    if payload.base_url is not None:
        settings.AIPAAS_BASE_URL = payload.base_url.strip()
    if payload.app_id is not None:
        settings.AIPAAS_APP_ID = payload.app_id.strip()
    if payload.sync_enabled is not None:
        settings.AIPAAS_SYNC_ENABLED = payload.sync_enabled
    if payload.sync_interval_minutes is not None:
        settings.AIPAAS_SYNC_INTERVAL_MINUTES = max(10, payload.sync_interval_minutes)
    return await get_config(_user=_user)


@router.post("/trigger")
async def trigger_sync(
    payload: AipaasSyncTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """手动触发一次 AIPAAS 日报拉取。"""
    if not settings.AIPAAS_BASE_URL:
        raise HTTPException(status_code=400, detail="AIPAAS_BASE_URL 未配置，请先在管理中心设置")
    if not settings.AIPAAS_APP_ID:
        raise HTTPException(status_code=400, detail="AIPAAS_APP_ID 未配置")

    target_date = None
    if payload.date:
        try:
            target_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式不正确，请使用 YYYY-MM-DD")

    user_list = [{"user_id": u.user_id, "user_name": u.user_name} for u in payload.users]

    result = await pull_aipaas_daily_reports(
        db,
        target_date=target_date,
        user_list=user_list,
    )
    return result


@router.get("/status")
async def sync_status(
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """同步状态检查。"""
    return {
        "configured": bool(settings.AIPAAS_BASE_URL and settings.AIPAAS_APP_ID),
        "enabled": settings.AIPAAS_SYNC_ENABLED,
        "interval_minutes": settings.AIPAAS_SYNC_INTERVAL_MINUTES,
        "base_url": settings.AIPAAS_BASE_URL or "(未配置)",
        "app_id": settings.AIPAAS_APP_ID or "(未配置)",
    }
