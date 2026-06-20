"""系统设置路由。

API Key 管理、钉钉配置、系统信息。
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import APIKeyRecord, DingtalkConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# API Key 管理
# ---------------------------------------------------------------------------


@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """API Key 列表（脱敏显示）。"""
    rows = (await db.execute(
        select(APIKeyRecord).order_by(APIKeyRecord.created_at.desc())
    )).scalars().all()
    return [_key_to_dict(k) for k in rows]


@router.post("/api-keys")
async def create_api_key(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """生成新 API Key。"""
    name = payload.get("name", "").strip()
    purpose = payload.get("purpose", "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")

    key_value = f"mk_{secrets.token_urlsafe(32)}"
    record = APIKeyRecord(
        name=name,
        purpose=purpose or "general",
        key_value=key_value,
        is_active=True,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    result = _key_to_dict(record)
    result["key_value"] = key_value  # 只在创建时返回完整 Key
    return result


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除 API Key。"""
    await db.execute(delete(APIKeyRecord).where(APIKeyRecord.id == key_id))
    return {"status": "ok"}


@router.put("/api-keys/{key_id}/toggle")
async def toggle_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """启用/禁用 API Key。"""
    key = (await db.execute(
        select(APIKeyRecord).where(APIKeyRecord.id == key_id)
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key 不存在")
    key.is_active = not key.is_active
    await db.flush()
    return _key_to_dict(key)


# ---------------------------------------------------------------------------
# 钉钉配置
# ---------------------------------------------------------------------------


@router.get("/dingtalk")
async def get_dingtalk_config(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取钉钉配置（脱敏）。"""
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if not row:
        return {
            "webhook_url": settings.DINGTALK_WEBHOOK_URL or "未配置",
            "webhook_masked": _mask_url(settings.DINGTALK_WEBHOOK_URL),
            "secret_masked": _mask_url(settings.DINGTALK_SECRET),
            "app_key": "",
            "app_secret": "",
            "jianyu_username": "",
            "jianyu_configured": False,
            "configured": bool(settings.DINGTALK_WEBHOOK_URL),
            "app_configured": False,
        }
    app_key = row.app_key or ""
    app_secret = row.app_secret or ""
    jianyu_user = row.jianyu_username or ""
    return {
        "webhook_url": row.webhook_url or "未配置",
        "webhook_masked": _mask_url(row.webhook_url),
        "secret_masked": _mask_url(row.secret),
        "app_key": app_key,
        "app_secret_masked": _mask_url(app_secret) if app_secret else "",
        "jianyu_username": jianyu_user,
        "jianyu_configured": bool(jianyu_user and (row.jianyu_password or "")),
        "configured": bool(row.webhook_url),
        "app_configured": bool(app_key and app_secret),
    }


@router.put("/dingtalk")
async def update_dingtalk_config(
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """更新钉钉配置。"""
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    webhook = payload.get("webhook_url", "").strip()
    secret = payload.get("secret", "").strip()
    app_key = payload.get("app_key", "").strip()
    app_secret = payload.get("app_secret", "").strip()
    jianyu_username = payload.get("jianyu_username", "").strip()
    jianyu_password = payload.get("jianyu_password", "").strip()

    if row:
        if webhook:
            row.webhook_url = webhook
        if secret:
            row.secret = secret
        if "app_key" in payload:
            row.app_key = app_key or None
        if "app_secret" in payload:
            row.app_secret = app_secret or None
        if "jianyu_username" in payload:
            row.jianyu_username = jianyu_username or None
        if "jianyu_password" in payload:
            row.jianyu_password = jianyu_password or None
    else:
        db.add(DingtalkConfig(
            webhook_url=webhook,
            secret=secret,
            app_key=app_key or None,
            app_secret=app_secret or None,
            jianyu_username=jianyu_username or None,
            jianyu_password=jianyu_password or None,
        ))
    return {"status": "ok"}


@router.post("/dingtalk/test")
async def test_dingtalk(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """测试钉钉推送（带 HMAC 签名）。"""
    from ..services import dingtalk_service

    result = await dingtalk_service.send_text(
        db,
        "营销数据驾驶舱 · 钉钉推送测试\n\n"
        "如收到此消息，说明配置正确。\n"
        "本次消息已启用 HMAC-SHA256 加签验证。",
    )
    return {"success": result["success"], "message": result["message"]}


# ---------------------------------------------------------------------------
# 系统信息
# ---------------------------------------------------------------------------


@router.get("/system")
async def get_system_info(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """系统信息概览。"""
    from .. import __version__

    # 数据库记录数统计
    from ..models import Activity, CrawlerItem, Staff, DailyExpress, ReportPage
    stats = {}
    for model, label in [
        (Activity, "activities"),
        (CrawlerItem, "crawler_items"),
        (Staff, "staff"),
        (DailyExpress, "express"),
        (ReportPage, "reports"),
    ]:
        count = (await db.execute(select(func.count(model.id)))).scalar_one() or 0
        stats[label] = count

    return {
        "version": __version__,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "llm_model": settings.LLM_MODEL,
        "data_stats": stats,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _key_to_dict(k: APIKeyRecord) -> dict[str, Any]:
    masked = k.key_value[:6] + "***" + k.key_value[-4:] if len(k.key_value) > 10 else "***"
    return {
        "id": k.id,
        "name": k.name,
        "purpose": k.purpose,
        "key_masked": masked,
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


def _mask_url(url: str | None) -> str:
    if not url:
        return "(not configured)"
    if len(url) <= 20:
        return url[:4] + "***"
    return url[:15] + "***" + url[-4:]
