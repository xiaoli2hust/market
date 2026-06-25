"""机器人中心路由。

第一版聚焦一个真实闭环：管理员可以把消息保存为草稿，或发送到管理中心
已配置的钉钉默认群；每次发送都保留状态、结果和操作日志。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import BotBroadcast, OperationLog
from ..services.dingtalk_service import send_markdown, send_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"])

_MESSAGE_TYPES = {"markdown", "text"}
_BROADCAST_STATUSES = {"draft", "sending", "sent", "failed"}
_TARGET_TYPE = "configured_group"
_TARGET_SUMMARY = "当前钉钉默认群（由管理中心配置）"
_MAX_TITLE_LENGTH = 120
_MAX_CONTENT_LENGTH = 5000


@router.get("/broadcasts")
async def list_broadcasts(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """查看机器人群发记录。"""

    conditions = []
    if status:
        clean_status = status.strip()
        if clean_status not in _BROADCAST_STATUSES:
            raise HTTPException(status_code=400, detail="群发状态不支持")
        conditions.append(BotBroadcast.status == clean_status)

    total = (
        await db.execute(select(func.count(BotBroadcast.id)).where(*conditions))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotBroadcast)
            .where(*conditions)
            .order_by(BotBroadcast.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_broadcast_to_dict(row) for row in rows]}


@router.post("/broadcasts")
async def create_broadcast(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """保存群发草稿。"""

    record = _build_broadcast(payload, _user)
    db.add(record)
    await db.flush()
    _log_operation(db, _user, "bot_broadcast_create", f"broadcast:{record.id}", record.title)
    await db.refresh(record)
    return _broadcast_to_dict(record)


@router.post("/broadcasts/send")
async def create_and_send_broadcast(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """创建群发记录并立即发送。"""

    record = _build_broadcast(payload, _user)
    db.add(record)
    await db.flush()
    _log_operation(db, _user, "bot_broadcast_create", f"broadcast:{record.id}", record.title)
    return await _send_broadcast(db, record, _user)


@router.post("/broadcasts/{broadcast_id}/send")
async def send_existing_broadcast(
    broadcast_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """发送已有草稿或失败记录。"""

    record = (
        await db.execute(select(BotBroadcast).where(BotBroadcast.id == broadcast_id))
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="群发记录不存在")
    if record.status not in {"draft", "failed"}:
        raise HTTPException(status_code=400, detail="该记录当前状态不能重复发送")
    return await _send_broadcast(db, record, _user)


def _build_broadcast(payload: dict[str, Any], user: dict[str, Any]) -> BotBroadcast:
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="消息标题不能为空")
    if len(title) > _MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息标题不能超过{_MAX_TITLE_LENGTH}字")
    if not content:
        raise HTTPException(status_code=400, detail="消息正文不能为空")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息正文不能超过{_MAX_CONTENT_LENGTH}字")

    message_type = str(payload.get("message_type") or "markdown").strip().lower()
    if message_type not in _MESSAGE_TYPES:
        raise HTTPException(status_code=400, detail="消息类型不支持")

    target_type = str(payload.get("target_type") or _TARGET_TYPE).strip()
    if target_type != _TARGET_TYPE:
        raise HTTPException(status_code=400, detail="当前版本仅支持发送到管理中心配置的钉钉默认群")

    target_payload = payload.get("target_payload")
    if target_payload is not None and not isinstance(target_payload, dict):
        raise HTTPException(status_code=400, detail="目标配置格式不正确")

    return BotBroadcast(
        title=title,
        content=content,
        message_type=message_type,
        target_type=_TARGET_TYPE,
        target_summary=_TARGET_SUMMARY,
        target_payload=target_payload or {},
        at_all=bool(payload.get("at_all")),
        status="draft",
        created_by=_user_id(user),
        created_by_name=_user_name(user),
    )


async def _send_broadcast(
    db: AsyncSession,
    record: BotBroadcast,
    user: dict[str, Any],
) -> dict[str, Any]:
    record.status = "sending"
    record.error_message = None
    record.result_message = None
    record.result_payload = None
    await db.flush()

    try:
        if record.message_type == "text":
            result = await send_text(db, record.content, is_at_all=record.at_all)
        else:
            result = await send_markdown(
                db,
                record.title,
                _markdown_text(record.title, record.content),
                is_at_all=record.at_all,
            )
    except Exception:
        logger.exception("bot broadcast send failed")
        result = {"success": False, "message": "机器人发送失败，请检查钉钉配置或稍后重试", "raw": {}}

    now = datetime.now(timezone.utc)
    record.sent_by = _user_id(user)
    record.sent_by_name = _user_name(user)
    record.sent_at = now
    record.result_message = str(result.get("message") or "")
    record.result_payload = result.get("raw") if isinstance(result.get("raw"), dict) else {}
    if result.get("success"):
        record.status = "sent"
        record.error_message = None
    else:
        record.status = "failed"
        record.error_message = record.result_message or "机器人发送失败"

    await db.flush()
    _log_operation(
        db,
        user,
        "bot_broadcast_send",
        f"broadcast:{record.id}",
        f"{record.status}:{record.result_message or record.title}",
    )
    await db.refresh(record)
    return _broadcast_to_dict(record)


def _markdown_text(title: str, content: str) -> str:
    clean = content.strip()
    if clean.startswith("#"):
        return clean
    return f"## {title.strip()}\n\n{clean}"


def _broadcast_to_dict(row: BotBroadcast) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "message_type": row.message_type,
        "target_type": row.target_type,
        "target_summary": row.target_summary,
        "target_payload": row.target_payload or {},
        "at_all": row.at_all,
        "status": row.status,
        "created_by": row.created_by,
        "created_by_name": row.created_by_name,
        "sent_by": row.sent_by,
        "sent_by_name": row.sent_by_name,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "result_message": row.result_message,
        "result_payload": row.result_payload or {},
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _user_id(user: dict[str, Any]) -> int | None:
    value = user.get("id")
    return int(value) if isinstance(value, int) or str(value or "").isdigit() else None


def _user_name(user: dict[str, Any]) -> str:
    return str(user.get("display_name") or user.get("username") or user.get("sub") or "系统用户")


def _log_operation(
    db: AsyncSession,
    user: dict[str, Any],
    action: str,
    target: str,
    detail: str,
) -> None:
    db.add(
        OperationLog(
            user_id=_user_id(user),
            username=_user_name(user),
            action=action,
            target=target,
            detail=detail[:1000],
        )
    )
