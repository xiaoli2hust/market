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

from ..auth import require_permission
from ..config import settings
from ..database import get_db
from ..models import APIKeyRecord, DingtalkConfig
from ..secret_store import decrypt_secret, encrypt_secret, hash_api_key, is_hashed_api_key
from ..validation import validate_http_url
from ..services.dingtalk_service import (
    normalize_custom_robot_secret,
    validate_custom_robot_webhook_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# API Key 管理
# ---------------------------------------------------------------------------


@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
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
    _user: dict = Depends(require_permission("management:settings")),
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
        key_value=hash_api_key(key_value),
        is_active=True,
        created_by=_user.get("id"),
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
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, str]:
    """删除 API Key。"""
    await db.execute(delete(APIKeyRecord).where(APIKeyRecord.id == key_id))
    return {"status": "ok"}


@router.put("/api-keys/{key_id}/toggle")
async def toggle_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
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

_DINGTALK_DELIVERY_ALIASES = {
    "": "",
    "webhook": "webhook",
    "custom_webhook": "webhook",
    "openapi": "openapi",
    "app_robot": "openapi",
    "application_robot": "openapi",
}


@router.get("/dingtalk")
async def get_dingtalk_config(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """获取钉钉配置（脱敏）。"""
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if not row:
        env_webhook = settings.DINGTALK_WEBHOOK_URL or ""
        env_secret = settings.DINGTALK_SECRET or ""
        return {
            "robot_mode": "custom_webhook",
            "send_channel": "webhook",
            "delivery_mode": "webhook",
            "webhook_url": env_webhook or "未配置",
            "webhook_masked": _mask_url(env_webhook),
            "secret_masked": _mask_url(env_secret),
            "security_policy": "sign" if env_secret else "keyword_or_none",
            "app_key": "",
            "app_secret": "",
            "app_id": "",
            "agent_id": "",
            "robot_code": "",
            "open_conversation_id": "",
            "cool_app_code": "",
            "callback_path": "/api/dingtalk/robot/callback",
            "receive_configured": False,
            "jianyu_username": "",
            "jianyu_configured": False,
            "configured": bool(env_webhook),
            "sign_configured": bool(env_secret),
            "app_configured": False,
            "openapi_configured": False,
            "capabilities": _dingtalk_capabilities(bool(env_webhook), bool(env_secret), False, False),
        }
    webhook_url = decrypt_secret(row.webhook_url)
    app_key = row.app_key or ""
    app_secret = decrypt_secret(row.app_secret)
    app_id = row.app_id or ""
    agent_id = row.agent_id or ""
    delivery_mode = row.delivery_mode or "webhook"
    robot_code = row.robot_code or ""
    open_conversation_id = row.open_conversation_id or ""
    cool_app_code = row.cool_app_code or ""
    jianyu_user = row.jianyu_username or ""
    jianyu_password = decrypt_secret(row.jianyu_password)
    jianyu_api_key = decrypt_secret(row.jianyu_api_key)
    secret = decrypt_secret(row.secret)
    app_configured = bool(app_key and app_secret)
    webhook_configured = bool(webhook_url)
    sign_configured = bool(secret)
    openapi_configured = bool(app_configured and robot_code and open_conversation_id)
    return {
        "robot_mode": "custom_webhook",
        "send_channel": delivery_mode,
        "delivery_mode": delivery_mode,
        "webhook_url": webhook_url or "未配置",
        "webhook_masked": _mask_url(webhook_url),
        "secret_masked": _mask_url(secret),
        "security_policy": "sign" if secret else "keyword_or_none",
        "app_key": app_key,
        "app_secret_masked": _mask_url(app_secret) if app_secret else "",
        "app_id": app_id,
        "agent_id": agent_id,
        "robot_code": robot_code,
        "open_conversation_id": open_conversation_id,
        "cool_app_code": cool_app_code,
        "callback_path": "/api/dingtalk/robot/callback",
        "receive_configured": bool(app_secret),
        "jianyu_username": jianyu_user,
        "jianyu_api_key_masked": _mask_url(jianyu_api_key) if jianyu_api_key else "",
        "jianyu_configured": bool(jianyu_api_key or (jianyu_user and jianyu_password)),
        "configured": webhook_configured,
        "sign_configured": sign_configured,
        "app_configured": app_configured,
        "openapi_configured": openapi_configured,
        "capabilities": _dingtalk_capabilities(
            webhook_configured,
            sign_configured,
            app_configured,
            openapi_configured,
        ),
    }


@router.put("/dingtalk")
async def update_dingtalk_config(
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """更新钉钉配置。"""
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    webhook = payload.get("webhook_url", "").strip()
    if "webhook_url" in payload:
        webhook = validate_http_url(webhook, "Webhook URL", allow_empty=True) or ""
        try:
            webhook = validate_custom_robot_webhook_url(webhook, allow_empty=True)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    secret = payload.get("secret", "").strip()
    if secret:
        try:
            secret = normalize_custom_robot_secret(secret)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    app_key = payload.get("app_key", "").strip()
    app_secret = payload.get("app_secret", "").strip()
    app_id = payload.get("app_id", "").strip()
    agent_id = payload.get("agent_id", "").strip()
    delivery_mode = payload.get("delivery_mode", "").strip()
    robot_code = payload.get("robot_code", "").strip()
    open_conversation_id = payload.get("open_conversation_id", "").strip()
    cool_app_code = payload.get("cool_app_code", "").strip()
    if delivery_mode not in _DINGTALK_DELIVERY_ALIASES:
        raise HTTPException(400, "unsupported dingtalk delivery mode")
    delivery_mode = _DINGTALK_DELIVERY_ALIASES[delivery_mode]
    jianyu_username = payload.get("jianyu_username", "").strip()
    jianyu_password = payload.get("jianyu_password", "").strip()
    jianyu_api_key = payload.get("jianyu_api_key", "").strip()

    if row:
        if "webhook_url" in payload:
            row.webhook_url = encrypt_secret(webhook) if webhook else None
        if secret:
            row.secret = encrypt_secret(secret)
        if "app_key" in payload:
            row.app_key = app_key or None
        if app_secret:
            row.app_secret = encrypt_secret(app_secret)
        if "app_id" in payload:
            row.app_id = app_id or None
        if "agent_id" in payload:
            row.agent_id = agent_id or None
        if "delivery_mode" in payload:
            row.delivery_mode = delivery_mode or "webhook"
        if "robot_code" in payload:
            row.robot_code = robot_code or None
        if "open_conversation_id" in payload:
            row.open_conversation_id = open_conversation_id or None
        if "cool_app_code" in payload:
            row.cool_app_code = cool_app_code or None
        if "jianyu_username" in payload:
            row.jianyu_username = jianyu_username or None
        if jianyu_password:
            row.jianyu_password = encrypt_secret(jianyu_password)
        if jianyu_api_key:
            row.jianyu_api_key = encrypt_secret(jianyu_api_key)
    else:
        db.add(DingtalkConfig(
            webhook_url=encrypt_secret(webhook) if webhook else None,
            secret=encrypt_secret(secret) if secret else None,
            app_key=app_key or None,
            app_secret=encrypt_secret(app_secret) if app_secret else None,
            app_id=app_id or None,
            agent_id=agent_id or None,
            delivery_mode=delivery_mode or "webhook",
            robot_code=robot_code or None,
            open_conversation_id=open_conversation_id or None,
            cool_app_code=cool_app_code or None,
            jianyu_username=jianyu_username or None,
            jianyu_password=encrypt_secret(jianyu_password) if jianyu_password else None,
            jianyu_api_key=encrypt_secret(jianyu_api_key) if jianyu_api_key else None,
        ))
    return {"status": "ok"}


@router.post("/dingtalk/test")
async def test_dingtalk(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """测试钉钉推送（带 HMAC 签名）。"""
    from ..services import dingtalk_service

    result = await dingtalk_service.send_text(
        db,
        "Market 数据采集中心 · 钉钉推送测试\n\n"
        "如收到此消息，说明配置正确。\n"
        "系统已按当前机器人安全配置完成发送。",
    )
    return {
        "success": result["success"],
        "message": result["message"],
        "raw": result.get("raw") or {},
    }


# ---------------------------------------------------------------------------
# 系统信息
# ---------------------------------------------------------------------------


@router.get("/system")
async def get_system_info(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:settings")),
) -> dict[str, Any]:
    """系统信息概览。"""
    from .. import __version__
    from ..services.llm_service import get_runtime_llm_config

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

    llm_config = await get_runtime_llm_config(db)

    return {
        "version": __version__,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "llm_model": llm_config["model"],
        "llm_config_source": llm_config["source"],
        "data_stats": stats,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _key_to_dict(k: APIKeyRecord) -> dict[str, Any]:
    if is_hashed_api_key(k.key_value):
        masked = "mk_***"
    else:
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


def _dingtalk_capabilities(
    webhook_configured: bool,
    sign_configured: bool,
    app_configured: bool,
    openapi_configured: bool,
) -> list[dict[str, Any]]:
    return [
        {
            "key": "webhook_text",
            "label": "文本通知",
            "ready": webhook_configured,
        },
        {
            "key": "webhook_markdown",
            "label": "Markdown 通知",
            "ready": webhook_configured,
        },
        {
            "key": "signing",
            "label": "加签安全",
            "ready": webhook_configured and sign_configured,
        },
        {
            "key": "app_token",
            "label": "企业应用凭证",
            "ready": app_configured,
        },
        {
            "key": "openapi_group",
            "label": "OpenAPI 群消息",
            "ready": openapi_configured,
        },
    ]
