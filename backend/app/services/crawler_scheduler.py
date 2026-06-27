"""Background scheduler for configured crawler runs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from ..database import SessionLocal
from ..models import CrawlerRunLog, ScheduleConfig

logger = logging.getLogger(__name__)
CRAWLER_FAILURE_RETRY_AFTER = timedelta(minutes=30)

_task: asyncio.Task | None = None
_state: dict[str, Any] = {
    "status": "stopped",
    "last_check_at": None,
    "last_run_at": None,
    "next_run_at": None,
    "crawler_next_runs": {},
    "last_error": None,
    "aipaas_last_sync_at": None,
    "aipaas_last_result": None,
}


def get_scheduler_state() -> dict[str, Any]:
    """Return a serializable snapshot of scheduler state."""

    return _serialize_datetimes(_state)


async def build_crawler_schedule_state(
    db,
    crawl_frequency_per_day: int,
    auto_crawl_enabled: bool,
) -> dict[str, Any]:
    """Build per-crawler schedule state from run logs."""

    from ..routers.crawler import CRAWLER_REGISTRY

    now = datetime.now(timezone.utc)
    frequency = max(int(crawl_frequency_per_day or 1), 1)
    interval = timedelta(hours=24 / frequency)
    crawler_next_runs: dict[str, dict[str, Any]] = {}
    latest_finished_values: list[datetime] = []
    next_run_values: list[datetime] = []
    due_names: list[str] = []

    for name, meta in CRAWLER_REGISTRY.items():
        latest_run = (
            await db.execute(
                select(CrawlerRunLog)
                .where(CrawlerRunLog.crawler_name == name)
                .order_by(CrawlerRunLog.finished_at.desc(), CrawlerRunLog.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        latest_finished = latest_run.finished_at if latest_run else None
        latest = _ensure_aware(latest_finished) if latest_finished else None
        retry_after = CRAWLER_FAILURE_RETRY_AFTER if latest_run and latest_run.status == "error" else interval
        next_run_at = (latest + min(interval, retry_after)) if latest else now
        due = bool(auto_crawl_enabled and (latest is None or now >= next_run_at))

        if latest:
            latest_finished_values.append(latest)
        if auto_crawl_enabled:
            next_run_values.append(next_run_at)
        if due:
            due_names.append(name)

        crawler_next_runs[name] = {
            "name": name,
            "category": meta.get("category"),
            "label": meta.get("label", name),
            "last_status": latest_run.status if latest_run else None,
            "last_run_at": latest,
            "next_run_at": next_run_at if auto_crawl_enabled else None,
            "due": due,
            "retry_after_minutes": int(retry_after.total_seconds() // 60),
        }

    return {
        "last_run_at": max(latest_finished_values) if latest_finished_values else None,
        "next_run_at": min(next_run_values) if next_run_values else None,
        "crawler_next_runs": crawler_next_runs,
        "due_names": due_names,
        "interval_hours": round(24 / frequency, 2),
    }


def start_crawler_scheduler() -> None:
    """Start the background crawler scheduler once per process."""

    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_scheduler_loop(), name="crawler-scheduler")
    _state["status"] = "started"
    logger.info("crawler scheduler started")


async def stop_crawler_scheduler() -> None:
    """Stop the background crawler scheduler."""

    global _task
    if not _task:
        _state["status"] = "stopped"
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    _state["status"] = "stopped"
    logger.info("crawler scheduler stopped")


async def _scheduler_loop() -> None:
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _state["status"] = "error"
            _state["last_error"] = str(exc)
            logger.exception("crawler scheduler tick failed")
        await asyncio.sleep(60)


async def _tick() -> None:
    from ..routers.crawler import execute_crawlers

    now = datetime.now(timezone.utc)
    _state["last_check_at"] = now

    async with SessionLocal() as db:
        config = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
        if not config or not config.auto_crawl_enabled:
            _state["status"] = "disabled"
            _state["next_run_at"] = None
        else:
            schedule = await build_crawler_schedule_state(
                db,
                config.crawl_frequency_per_day,
                bool(config.auto_crawl_enabled),
            )
            _state["last_run_at"] = schedule["last_run_at"]
            _state["next_run_at"] = schedule["next_run_at"]
            _state["crawler_next_runs"] = schedule["crawler_next_runs"]

            due_names = schedule["due_names"]
            if due_names:
                _state["status"] = "running"
                _state["last_error"] = None
                await execute_crawlers(db, due_names, trigger_source="schedule")
                _state["last_run_at"] = datetime.now(timezone.utc)

        # AIPAAS 定时拉取
        await _maybe_sync_aipaas(db)

        if _state["status"] not in ("running", "error"):
            _state["status"] = "waiting"


async def _maybe_sync_aipaas(db) -> None:
    """检查是否到了 AIPAAS 同步时间，如果是则执行拉取。"""
    from ..config import settings
    from .aipaas_service import pull_aipaas_daily_reports

    if not settings.AIPAAS_SYNC_ENABLED:
        return
    if not settings.AIPAAS_BASE_URL or not settings.AIPAAS_APP_ID:
        return

    interval = timedelta(minutes=settings.AIPAAS_SYNC_INTERVAL_MINUTES)
    last_sync = _state.get("aipaas_last_sync_at")
    if last_sync and isinstance(last_sync, datetime):
        if (datetime.now(timezone.utc) - last_sync) < interval:
            return  # 还没到同步间隔

    try:
        logger.info("AIPAAS 定时同步开始")
        # 注意：自动同步需要预配置用户列表
        # 暂时仅记录状态，用户需通过 API 手动触发或配置用户列表
        _state["aipaas_last_sync_at"] = datetime.now(timezone.utc)
        _state["aipaas_last_result"] = {"status": "skipped", "message": "自动同步需要配置用户列表，请通过 POST /api/aipaas-sync/trigger 手动触发"}
        logger.info("AIPAAS 定时同步完成（需要配置用户列表后手动触发）")
    except Exception as exc:
        _state["aipaas_last_result"] = {"status": "error", "message": str(exc)[:200]}
        logger.error("AIPAAS 定时同步失败: %s", exc)


def _serialize_datetimes(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_datetimes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_datetimes(item) for item in value]
    return value


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
