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
from ..models import DailyReportFile, Staff

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_REQUEST_TIMEOUT = 30


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
    if not settings.AIPAAS_BASE_URL:
        return {"status": "skipped", "message": "AIPAAS_BASE_URL 未配置"}
    if not settings.AIPAAS_APP_ID:
        return {"status": "skipped", "message": "AIPAAS_APP_ID 未配置"}

    report_date = target_date or datetime.now(tz=LOCAL_TZ).date()
    date_str = report_date.strftime("%Y%m%d")

    stats = {
        "date": report_date.isoformat(),
        "total_users": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    if not user_list:
        return {"status": "skipped", "message": "用户列表为空，请配置需要同步的人员"}

    stats["total_users"] = len(user_list)

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for user in user_list:
            user_id = str(user.get("user_id", "")).strip()
            user_name = str(user.get("user_name", "")).strip()
            if not user_id or not user_name:
                stats["skipped"] += 1
                continue

            try:
                result = await _pull_single_user(
                    client, db,
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
    return stats


async def _pull_single_user(
    client: httpx.AsyncClient,
    db: AsyncSession,
    *,
    user_id: str,
    user_name: str,
    date_str: str,
    report_date: date,
) -> str:
    """拉取单个用户的日报数据。返回 success / no_data / error。"""

    file_path = f"/user_chat/{user_id}_{user_name}_{date_str}.json"
    url = f"{settings.AIPAAS_BASE_URL.rstrip('/')}/SkillsApp/api/v1/vfs/read"
    params = {"app_id": settings.AIPAAS_APP_ID, "file_path": file_path}

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
