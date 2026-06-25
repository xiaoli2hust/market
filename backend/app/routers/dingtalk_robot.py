"""DingTalk robot receive-message callback.

This endpoint receives text messages sent to the DingTalk app robot and turns
them into daily-report source records.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, unquote_plus
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Activity, DailyReportFile, DingtalkConfig, Staff
from ..secret_store import decrypt_secret
from ..services.llm_service import parse_daily_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dingtalk/robot", tags=["dingtalk-robot"])

_SIGNATURE_WINDOW_SECONDS = 60 * 60
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


async def verify_dingtalk_signature_dependency(
    timestamp: str | None = Header(default=None),
    sign: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Access control for DingTalk robot callbacks."""

    app_secret = await _load_app_secret(db)
    if not app_secret:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="钉钉应用 AppSecret 未配置",
        )
    _verify_dingtalk_signature(timestamp, sign, app_secret)


@router.post("/callback")
async def receive_robot_message(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _verified: None = Depends(verify_dingtalk_signature_dependency),
) -> dict[str, Any]:
    """Receive DingTalk robot messages and append text to the sender's daily report."""

    payload = await request.json()

    message = _extract_text_message(payload)
    if not message["content"]:
        return _reply_text("我现在只接收文本日报。请直接发送今天的工作内容。")

    report_date = _message_date(payload)
    result = await _append_and_parse_daily_report(
        db,
        user_id=message["user_id"],
        user_name=message["user_name"],
        report_date=report_date,
        content=message["content"],
        message_time=message["message_time"],
        raw_payload=payload,
    )

    if result["parse_status"] == "success":
        return _reply_text(f"已收到 {message['user_name']} 的日报，解析出 {result['activities_count']} 条活动。")
    if result["parse_status"] == "empty":
        return _reply_text("我收到了消息，但没有识别到日报正文。请直接发送今天做了什么。")
    return _reply_text(f"日报已保存，但自动解析未完成：{result['message'] or '请稍后在系统中查看'}")


def _verify_dingtalk_signature(timestamp: str | None, sign: str | None, secret: str) -> None:
    if not timestamp or not sign:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少钉钉签名")
    try:
        ts_ms = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="钉钉时间戳无效") from exc

    now_ms = int(time.time() * 1000)
    if abs(now_ms - ts_ms) > _SIGNATURE_WINDOW_SECONDS * 1000:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="钉钉签名已过期")

    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    candidates = {sign, unquote(sign), unquote_plus(sign)}
    if not any(hmac.compare_digest(expected, value) for value in candidates):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="钉钉签名校验失败")


async def _load_app_secret(db: AsyncSession) -> str:
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if not row:
        return ""
    return decrypt_secret(row.app_secret) or ""


def _extract_text_message(payload: dict[str, Any]) -> dict[str, str]:
    msgtype = str(payload.get("msgtype") or payload.get("msgType") or "").lower()
    content = ""
    if msgtype == "text" or isinstance(payload.get("text"), dict):
        content = str((payload.get("text") or {}).get("content") or "").strip()
    if not content:
        content = str(payload.get("content") or payload.get("textContent") or "").strip()

    user_id = (
        str(payload.get("senderStaffId") or "").strip()
        or str(payload.get("senderId") or "").strip()
        or str(payload.get("senderUnionId") or "").strip()
        or "unknown_dingtalk_user"
    )
    user_name = (
        str(payload.get("senderNick") or "").strip()
        or str(payload.get("senderName") or "").strip()
        or user_id
    )
    message_time = str(payload.get("createAt") or payload.get("createTime") or "").strip()
    return {
        "content": _clean_daily_text(content),
        "user_id": user_id[:50],
        "user_name": user_name[:50],
        "message_time": message_time,
    }


def _clean_daily_text(content: str) -> str:
    text = " ".join(str(content or "").split())
    prefixes = ("日报", "今日日报", "今天日报", "工作日报", "我的日报")
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip("：: ，,")
            break
    return text


def _message_date(payload: dict[str, Any]) -> datetime.date:
    raw = payload.get("createAt") or payload.get("createTime")
    if raw:
        try:
            value = int(raw)
            if value > 10_000_000_000:
                return datetime.fromtimestamp(value / 1000, tz=LOCAL_TIMEZONE).date()
            return datetime.fromtimestamp(value, tz=LOCAL_TIMEZONE).date()
        except (TypeError, ValueError, OSError):
            pass
    return datetime.now(tz=LOCAL_TIMEZONE).date()


async def _append_and_parse_daily_report(
    db: AsyncSession,
    *,
    user_id: str,
    user_name: str,
    report_date,
    content: str,
    message_time: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    staff = await _get_or_create_staff(db, user_name)
    report_file = await _get_or_create_report_file(db, user_id, user_name, report_date)

    raw_content = dict(report_file.raw_content or {})
    conversations = list(raw_content.get("conversations") or [])
    msg_id = raw_payload.get("msgId") or raw_payload.get("messageId")
    if msg_id and any(str(item.get("msg_id") or "") == str(msg_id) for item in conversations):
        activity_ids = (
            await db.execute(
                select(Activity.id).where(Activity.staff_id == staff.id, Activity.report_date == report_date)
            )
        ).scalars().all()
        return {
            "file_id": report_file.id,
            "parse_status": report_file.parse_status,
            "activities_count": len(activity_ids),
            "message": "duplicate message ignored",
        }
    conversations.append({
        "time": message_time or datetime.now(tz=LOCAL_TIMEZONE).isoformat(timespec="seconds"),
        "question": content,
        "answer": "",
        "source": "dingtalk_robot",
        "msg_id": msg_id,
    })
    raw_content.update({
        "user_id": user_id,
        "user_name": user_name,
        "date": report_date.isoformat(),
        "timezone": "Asia/Shanghai",
        "conversation_count": len(conversations),
        "conversations": conversations,
        "source": "dingtalk_robot",
        "last_updated": datetime.now(tz=timezone.utc).isoformat(),
    })
    report_file.raw_content = raw_content
    report_file.parse_status = "pending"
    report_file.parsed_at = None
    report_file.error_message = None
    await db.flush()

    await db.execute(delete(Activity).where(Activity.staff_id == staff.id, Activity.report_date == report_date))
    report_text = "\n\n".join(
        str(item.get("question") or "").strip()
        for item in conversations
        if str(item.get("question") or "").strip()
    )

    activities_count = 0
    parse_status = "success"
    error_message: str | None = None
    if not report_text:
        parse_status = "empty"
        error_message = "日报正文为空"
    else:
        try:
            activities = await parse_daily_report(user_name=user_name, report_text=report_text, db=db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("钉钉日报解析失败: %s", exc)
            activities = []
            parse_status = "failed"
            error_message = f"llm error: {exc}"
        if activities:
            for item in activities:
                db.add(Activity(
                    staff_id=staff.id,
                    report_date=report_date,
                    activity_type=item["activity_type"],
                    target=item.get("target"),
                    opportunity=item.get("opportunity"),
                    description=item.get("description"),
                    confidence=float(item.get("confidence") or 0.8),
                    is_reviewed=False,
                    source_file_id=report_file.id,
                ))
            activities_count = len(activities)
        elif parse_status == "success":
            parse_status = "failed"
            error_message = "LLM 未返回任何活动（可能未配置 Key 或解析失败）"

    report_file.parse_status = parse_status
    report_file.parsed_at = datetime.now(tz=timezone.utc)
    report_file.error_message = error_message
    await db.commit()
    return {
        "file_id": report_file.id,
        "parse_status": parse_status,
        "activities_count": activities_count,
        "message": error_message,
    }


async def _get_or_create_staff(db: AsyncSession, user_name: str) -> Staff:
    name = (user_name or "").strip() or "钉钉用户"
    row = (await db.execute(select(Staff).where(Staff.name == name))).scalar_one_or_none()
    if row:
        return row
    staff = Staff(name=name, role="销售", department="", is_active=True)
    db.add(staff)
    await db.flush()
    return staff


async def _get_or_create_report_file(
    db: AsyncSession,
    user_id: str,
    user_name: str,
    report_date,
) -> DailyReportFile:
    row = (
        await db.execute(
            select(DailyReportFile).where(
                DailyReportFile.user_id == user_id,
                DailyReportFile.file_date == report_date,
            )
        )
    ).scalar_one_or_none()
    if row:
        row.user_name = user_name
        return row

    record = DailyReportFile(
        user_id=user_id,
        user_name=user_name,
        file_name=f"dingtalk_{user_id}_{report_date.isoformat()}.json",
        file_date=report_date,
        raw_content={
            "user_id": user_id,
            "user_name": user_name,
            "date": report_date.isoformat(),
            "timezone": "Asia/Shanghai",
            "conversation_count": 0,
            "conversations": [],
            "source": "dingtalk_robot",
        },
        parse_status="pending",
    )
    db.add(record)
    await db.flush()
    return record


def _reply_text(content: str) -> dict[str, Any]:
    return {"msgtype": "text", "text": {"content": content}}
