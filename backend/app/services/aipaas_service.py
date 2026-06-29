"""AIPAAS 日报聊天日志拉取服务。

定时从 AIPAAS 系统拉取所有用户的日报聊天记录，
转换后写入 DailyReportFile 表并由 LLM 自动解析为活动记录。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import AipaasConfig, DailyReportFile, Staff

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_REQUEST_TIMEOUT = 30


def normalize_aipaas_users(users: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Return a clean, de-duplicated AIPAAS user list."""

    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in users or []:
        user_id = str(item.get("user_id") or "").strip()
        user_name = str(item.get("user_name") or "").strip()
        if not user_id or not user_name or user_id in seen:
            continue
        cleaned.append({"user_id": user_id[:80], "user_name": user_name[:80]})
        seen.add(user_id)
    return cleaned


async def get_runtime_aipaas_config(db: AsyncSession) -> dict[str, Any]:
    """Load effective AIPAAS config, preferring management-center settings."""

    row = (await db.execute(select(AipaasConfig).limit(1))).scalar_one_or_none()
    if row:
        return {
            "base_url": row.base_url or settings.AIPAAS_BASE_URL,
            "app_id": row.app_id or settings.AIPAAS_APP_ID,
            "sync_enabled": bool(row.sync_enabled),
            "sync_interval_minutes": max(int(row.sync_interval_minutes or 60), 10),
            "sync_users": normalize_aipaas_users(row.sync_users or []),
            "last_sync_at": row.last_sync_at,
            "last_sync_result": row.last_sync_result or None,
            "source": "management",
        }
    return {
        "base_url": settings.AIPAAS_BASE_URL,
        "app_id": settings.AIPAAS_APP_ID,
        "sync_enabled": bool(settings.AIPAAS_SYNC_ENABLED),
        "sync_interval_minutes": max(int(settings.AIPAAS_SYNC_INTERVAL_MINUTES or 60), 10),
        "sync_users": [],
        "last_sync_at": None,
        "last_sync_result": None,
        "source": "env",
    }


async def upsert_runtime_aipaas_config(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist AIPAAS config in the management-center database."""

    row = (await db.execute(select(AipaasConfig).limit(1))).scalar_one_or_none()
    if row is None:
        row = AipaasConfig(
            base_url=settings.AIPAAS_BASE_URL or None,
            app_id=settings.AIPAAS_APP_ID or None,
            sync_enabled=bool(settings.AIPAAS_SYNC_ENABLED),
            sync_interval_minutes=max(int(settings.AIPAAS_SYNC_INTERVAL_MINUTES or 60), 10),
            sync_users=[],
        )
        db.add(row)
        await db.flush()

    if "base_url" in payload:
        row.base_url = str(payload.get("base_url") or "").strip() or None
    if "app_id" in payload:
        row.app_id = str(payload.get("app_id") or "").strip() or None
    if "sync_enabled" in payload:
        row.sync_enabled = bool(payload.get("sync_enabled"))
    if "sync_interval_minutes" in payload and payload.get("sync_interval_minutes") is not None:
        row.sync_interval_minutes = max(int(payload.get("sync_interval_minutes") or 60), 10)
    if "sync_users" in payload:
        row.sync_users = normalize_aipaas_users(payload.get("sync_users") or [])

    await db.flush()
    return await get_runtime_aipaas_config(db)


async def record_aipaas_sync_result(db: AsyncSession, result: dict[str, Any]) -> None:
    """Persist latest AIPAAS sync status for the management center."""

    row = (await db.execute(select(AipaasConfig).limit(1))).scalar_one_or_none()
    if row is None:
        row = AipaasConfig(
            base_url=settings.AIPAAS_BASE_URL or None,
            app_id=settings.AIPAAS_APP_ID or None,
            sync_enabled=bool(settings.AIPAAS_SYNC_ENABLED),
            sync_interval_minutes=max(int(settings.AIPAAS_SYNC_INTERVAL_MINUTES or 60), 10),
            sync_users=[],
        )
        db.add(row)
        await db.flush()
    row.last_sync_at = datetime.now(timezone.utc)
    row.last_sync_result = result
    await db.flush()


async def pull_aipaas_daily_reports(
    db: AsyncSession,
    *,
    target_date: date | None = None,
    user_list: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """从 AIPAAS 拉取日报数据并写入系统。

    Parameters
    ----------
    db:
        数据库会话。
    target_date:
        要拉取的日期，默认今天。
    user_list:
        用户列表 [{"user_id": "33342401", "user_name": "胡夏天"}, ...]。
        如果为空则跳过（需要知道拉谁）。

    Returns
    -------
    拉取结果统计。
    """
    config = await get_runtime_aipaas_config(db)
    base_url = str(config.get("base_url") or "").strip()
    app_id = str(config.get("app_id") or "").strip()
    if not base_url:
        result = {"status": "skipped", "message": "AIPAAS 地址未配置"}
        await record_aipaas_sync_result(db, result)
        return result
    if not app_id:
        result = {"status": "skipped", "message": "AIPAAS App ID 未配置"}
        await record_aipaas_sync_result(db, result)
        return result

    report_date = target_date or datetime.now(tz=LOCAL_TZ).date()
    date_str = report_date.strftime("%Y%m%d")

    stats = {
        "status": "completed",
        "date": report_date.isoformat(),
        "total_users": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    users = normalize_aipaas_users(user_list) or normalize_aipaas_users(config.get("sync_users") or [])
    if not users:
        result = {"status": "skipped", "message": "用户列表为空，请在管理中心配置需要同步的人员"}
        await record_aipaas_sync_result(db, result)
        return result

    stats["total_users"] = len(users)

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for user in users:
            user_id = str(user.get("user_id", "")).strip()
            user_name = str(user.get("user_name", "")).strip()
            if not user_id or not user_name:
                stats["skipped"] += 1
                continue

            try:
                result = await _pull_single_user(
                    client, db,
                    base_url=base_url,
                    app_id=app_id,
                    user_id=user_id,
                    user_name=user_name,
                    date_str=date_str,
                    report_date=report_date,
                )
                if result == "success":
                    stats["success"] += 1
                elif result == "no_data":
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
                stats["details"].append({"user_id": user_id, "user_name": user_name, "result": result})
            except Exception as exc:
                logger.error("AIPAAS 拉取失败 user=%s(%s): %s", user_name, user_id, exc)
                stats["failed"] += 1
                stats["details"].append({"user_id": user_id, "user_name": user_name, "result": "error", "error": str(exc)[:200]})

    logger.info(
        "AIPAAS 同步完成: date=%s total=%d success=%d failed=%d skipped=%d",
        report_date, stats["total_users"], stats["success"], stats["failed"], stats["skipped"],
    )
    await record_aipaas_sync_result(db, stats)
    return stats


async def _pull_single_user(
    client: httpx.AsyncClient,
    db: AsyncSession,
    *,
    base_url: str,
    app_id: str,
    user_id: str,
    user_name: str,
    date_str: str,
    report_date: date,
) -> str:
    """拉取单个用户的日报数据。返回 success / no_data / error。"""

    file_path = f"/user_chat/{user_id}_{user_name}_{date_str}.json"
    url = f"{base_url.rstrip('/')}/SkillsApp/api/v1/vfs/read"
    params = {"app_id": app_id, "file_path": file_path}

    response = await client.get(url, params=params)

    if response.status_code == 404:
        logger.debug("AIPAAS 无数据: user=%s date=%s", user_name, date_str)
        return "no_data"
    response.raise_for_status()

    data = response.json()
    if not data or not data.get("conversations"):
        return "no_data"

    # 转换为系统格式并写入
    conversations = _normalize_conversations(data.get("conversations", []))
    if not conversations:
        return "no_data"

    raw_content = {
        "user_id": str(data.get("user_id") or user_id),
        "user_name": str(data.get("user_name") or user_name),
        "date": report_date.isoformat(),
        "timezone": str(data.get("timezone") or "Asia/Shanghai"),
        "created_at": str(data.get("created_at") or ""),
        "last_updated": str(data.get("last_updated") or ""),
        "conversation_count": len(conversations),
        "conversations": conversations,
        "source": "aipaas_pull",
    }

    await _upsert_report(db, raw_content, report_date)
    return "success"


def _normalize_conversations(raw_list: list[dict[str, Any]]) -> list[dict[str, str]]:
    """标准化对话列表格式。"""
    result = []
    for item in raw_list:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        time_str = str(item.get("time") or "").strip()
        if question:  # 只保留有用户输入的记录
            result.append({
                "time": time_str,
                "question": question,
                "answer": answer,
                "source": "aipaas",
            })
    return result


async def _upsert_report(
    db: AsyncSession,
    raw_content: dict[str, Any],
    report_date: date,
) -> DailyReportFile:
    """将日报数据写入 DailyReportFile，复用现有去重逻辑。"""
    user_id = raw_content["user_id"]
    user_name = raw_content["user_name"]
    file_name = f"aipaas_{user_id}_{report_date.isoformat()}.json"

    stmt = select(DailyReportFile).where(
        DailyReportFile.user_id == user_id,
        DailyReportFile.file_date == report_date,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is None:
        record = DailyReportFile(
            user_id=user_id,
            user_name=user_name,
            file_name=file_name,
            file_date=report_date,
            raw_content=raw_content,
            parse_status="pending",
        )
        db.add(record)
    else:
        existing.user_name = user_name
        existing.file_name = file_name
        existing.raw_content = raw_content
        existing.parse_status = "pending"
        existing.error_message = None

    await db.flush()

    # 确保 Staff 存在
    staff = (await db.execute(select(Staff).where(Staff.name == user_name))).scalar_one_or_none()
    if staff is None:
        staff = Staff(name=user_name, role="销售", department="", is_active=True)
        db.add(staff)
        await db.flush()
        logger.info("AIPAAS 同步自动创建 staff: %s", user_name)

    # 触发 LLM 解析（异步，不阻塞）
    try:
        from ..services.llm_service import parse_daily_report
        report_text = "\n".join(
            conv["question"] for conv in raw_content.get("conversations", []) if conv.get("question")
        )
        if report_text.strip():
            activities = await parse_daily_report(report_text, report_date.isoformat())
            if activities:
                existing_or_new = (await db.execute(
                    select(DailyReportFile).where(
                        DailyReportFile.user_id == user_id,
                        DailyReportFile.file_date == report_date,
                    )
                )).scalar_one()
                existing_or_new.parse_status = "success"
                existing_or_new.parsed_at = datetime.now(timezone.utc)
                logger.info(
                    "AIPAAS 解析成功: user=%s date=%s activities=%d",
                    user_name, report_date, len(activities),
                )
            else:
                existing_or_new = (await db.execute(
                    select(DailyReportFile).where(
                        DailyReportFile.user_id == user_id,
                        DailyReportFile.file_date == report_date,
                    )
                )).scalar_one()
                existing_or_new.parse_status = "empty"
    except Exception as exc:
        logger.warning("AIPAAS LLM 解析失败 user=%s: %s", user_name, exc)
        record_after = (await db.execute(
            select(DailyReportFile).where(
                DailyReportFile.user_id == user_id,
                DailyReportFile.file_date == report_date,
            )
        )).scalar_one()
        record_after.parse_status = "error"
        record_after.error_message = str(exc)[:500]

    return record_after
