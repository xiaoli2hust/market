"""AIPAAS 日报同步管理路由。

提供手动触发拉取、配置查看、用户列表管理等接口。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..services.aipaas_service import (
    get_runtime_aipaas_config,
    normalize_aipaas_users,
    pull_aipaas_daily_reports,
    upsert_runtime_aipaas_config,
)
from ..validation import validate_http_url

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
    sync_users: list[AipaasUserItem] | None = None


# ---------- 接口 ----------


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """查看 AIPAAS 同步配置。"""
    config = await get_runtime_aipaas_config(db)
    return _public_config(config)


@router.put("/config")
async def update_config(
    payload: AipaasConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """更新 AIPAAS 同步配置。"""
    update_payload: dict[str, Any] = {}
    if payload.base_url is not None:
        update_payload["base_url"] = validate_http_url(payload.base_url, "AIPAAS 地址", allow_empty=True)
    if payload.app_id is not None:
        update_payload["app_id"] = payload.app_id.strip()
    if payload.sync_enabled is not None:
        update_payload["sync_enabled"] = payload.sync_enabled
    if payload.sync_interval_minutes is not None:
        update_payload["sync_interval_minutes"] = max(10, payload.sync_interval_minutes)
    if payload.sync_users is not None:
        update_payload["sync_users"] = [
            {"user_id": item.user_id, "user_name": item.user_name}
            for item in payload.sync_users
        ]
    config = await upsert_runtime_aipaas_config(db, update_payload)
    return _public_config(config)


@router.post("/trigger")
async def trigger_sync(
    payload: AipaasSyncTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """手动触发一次 AIPAAS 日报拉取。"""
    config = await get_runtime_aipaas_config(db)
    if not config.get("base_url"):
        raise HTTPException(status_code=400, detail="AIPAAS 地址未配置，请先在管理中心设置")
    if not config.get("app_id"):
        raise HTTPException(status_code=400, detail="AIPAAS App ID 未配置")

    target_date = None
    if payload.date:
        try:
            target_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式不正确，请使用 YYYY-MM-DD")

    user_list = normalize_aipaas_users(
        [{"user_id": u.user_id, "user_name": u.user_name} for u in payload.users]
    )

    result = await pull_aipaas_daily_reports(
        db,
        target_date=target_date,
        user_list=user_list,
    )
    return result


@router.get("/status")
async def sync_status(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """同步状态检查。"""
    config = await get_runtime_aipaas_config(db)
    return {
        **_public_config(config),
        "configured": bool(config.get("base_url") and config.get("app_id")),
    }


def _public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_url": config.get("base_url") or "",
        "app_id": config.get("app_id") or "",
        "sync_enabled": bool(config.get("sync_enabled")),
        "sync_interval_minutes": int(config.get("sync_interval_minutes") or 60),
        "sync_users": normalize_aipaas_users(config.get("sync_users") or []),
        "last_sync_at": config.get("last_sync_at").isoformat() if config.get("last_sync_at") else None,
        "last_sync_result": config.get("last_sync_result"),
        "source": config.get("source") or "management",
    }
