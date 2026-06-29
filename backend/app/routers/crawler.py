"""市场洞察 + 爬虫管理路由。

提供：
- GET /intelligence/        → 市场信号列表（分页 + 筛选）
- GET /intelligence/stats   → 各分类统计
- GET /intelligence/{id}    → 单条详情
- GET /intelligence/categories → 分类字典
- GET /crawlers/status      → 爬虫状态
- POST /crawlers/{name}/run → 手动触发爬虫
- POST /crawlers/run-all    → 手动触发全部
"""

from __future__ import annotations

import logging
import re
import uuid
import asyncio
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import SessionLocal, get_db
from ..models import (
    CrawlerItem,
    CrawlerRunLog,
    CrawlerSource,
    CrawlerTaskLock,
    CrawlerTaskRun,
    KeywordConfig,
    ScheduleConfig,
)
from ..schemas import (
    CrawlerItemOut,
    CrawlerRunLogOut,
    CrawlerStatusOut,
    CrawlRunResult,
    IntelligenceStats,
)
from ..crawlers.config import (
    AI_KEYWORDS,
    CATEGORIES,
    COMPETITOR_KEYWORDS,
    JIANYU_SEARCH_KEYWORDS_SELECTED,
    MARKET_KEYWORDS,
    POLICY_KEYWORDS,
)
from ..crawlers.base import BaseCrawler, CrawlStats
from ..crawlers.diagnostics import build_crawler_run_diagnostics
from ..crawlers.policy import build_source_strategy_profile, normalize_crawl_policy, policy_summary
from ..crawlers.market_crawler import MarketCrawler
from ..crawlers.competitor_crawler import CompetitorCrawler
from ..crawlers.ai_crawler import AICrawler
from ..crawlers.bidding_crawler import JianyuBiddingCrawler
from ..crawlers.official_crawler import PolicyCrawler

logger = logging.getLogger(__name__)
LOCAL_TZ = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 路由器
# ---------------------------------------------------------------------------

intelligence_router = APIRouter(prefix="/intelligence", tags=["intelligence"])
crawler_router = APIRouter(prefix="/crawlers", tags=["crawlers"])

# 爬虫注册表
CRAWLER_REGISTRY: dict[str, dict[str, Any]] = {
    "bidding": {
        "class": JianyuBiddingCrawler,
        "category": "bidding",
        "label": "标讯雷达",
        "keywords": JIANYU_SEARCH_KEYWORDS_SELECTED,
    },
    "market": {
        "class": MarketCrawler,
        "category": "news",
        "label": "市场线索",
        "keywords": MARKET_KEYWORDS,
    },
    "policy": {
        "class": PolicyCrawler,
        "category": "policy",
        "label": "政策研判",
        "keywords": POLICY_KEYWORDS,
    },
    "competitor": {
        "class": CompetitorCrawler,
        "category": "competitor",
        "label": "竞对监控",
        "keywords": COMPETITOR_KEYWORDS,
    },
    "ai": {
        "class": AICrawler,
        "category": "ai",
        "label": "行业知识",
        "keywords": AI_KEYWORDS,
    },
}

# 运行状态缓存（进程内）
_crawler_run_status: dict[str, dict[str, Any]] = {}
CRAWLER_TASK_LOCK_TTL = timedelta(minutes=60)
CRAWLER_TASK_HEARTBEAT_INTERVAL_SECONDS = 30


# ---------------------------------------------------------------------------
# 市场洞察 API
# ---------------------------------------------------------------------------


@intelligence_router.get("/")
async def list_intelligence(
    category: str | None = Query(None, description="分类筛选：bidding/policy/news/competitor/ai"),
    keyword: str | None = Query(None, description="关键词搜索"),
    source: str | None = Query(None, description="来源筛选"),
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    sort_by: str = Query("published_at", description="排序字段：published_at/amount/relevance/created_at"),
    sort_order: str = Query("desc", description="排序方向：asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("intelligence:view")),
) -> dict[str, Any]:
    """市场信号列表，支持多维度筛选与分页。"""

    threshold = await _load_relevance_threshold(db)
    conditions = []
    if category:
        if category not in CATEGORIES:
            return {"total": 0, "items": [], "page": page, "page_size": page_size}
        conditions.append(CrawlerItem.category == category)
        if category == "bidding":
            conditions.append(CrawlerItem.relevance_score >= threshold)
    else:
        conditions.append(CrawlerItem.category.in_(list(CATEGORIES.keys())))
        conditions.append(_visible_intelligence_condition(threshold))
    if source:
        conditions.append(CrawlerItem.source == source)
    if keyword:
        kw_pattern = f"%{keyword}%"
        conditions.append(
            CrawlerItem.title.ilike(kw_pattern)
            | CrawlerItem.summary.ilike(kw_pattern)
            | CrawlerItem.content.ilike(kw_pattern)
        )
    if start_date:
        try:
            conditions.append(CrawlerItem.published_at >= date.fromisoformat(start_date))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="起始日期格式应为 YYYY-MM-DD") from exc
    if end_date:
        try:
            conditions.append(CrawlerItem.published_at <= date.fromisoformat(end_date))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="结束日期格式应为 YYYY-MM-DD") from exc

    # 总数
    count_stmt = select(func.count(CrawlerItem.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    # 列表
    list_stmt = select(CrawlerItem)
    if conditions:
        list_stmt = list_stmt.where(*conditions)
    offset = (page - 1) * page_size
    normalized_sort_by = _normalize_intelligence_sort_by(sort_by)
    normalized_sort_order = "asc" if str(sort_order).lower() == "asc" else "desc"
    list_stmt = list_stmt.order_by(*_intelligence_order_by(normalized_sort_by, normalized_sort_order))
    list_stmt = list_stmt.offset(offset).limit(page_size)
    rows = (await db.execute(list_stmt)).scalars().all()
    items = [_crawler_item_to_dict(r) for r in rows]

    return {"total": total, "items": items, "page": page, "page_size": page_size}


@intelligence_router.get("/stats")
async def intelligence_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("intelligence:view")),
) -> dict[str, Any]:
    """各分类统计。"""

    active_categories = list(CATEGORIES.keys())
    threshold = await _load_relevance_threshold(db)

    # 总数
    visible_condition = _visible_intelligence_condition(threshold)
    total = (
        await db.execute(
            select(func.count(CrawlerItem.id)).where(
                CrawlerItem.category.in_(active_categories),
                visible_condition,
            )
        )
    ).scalar_one() or 0

    # 按分类统计
    cat_stmt = (
        select(CrawlerItem.category, func.count(CrawlerItem.id))
        .where(CrawlerItem.category.in_(active_categories), visible_condition)
        .group_by(CrawlerItem.category)
    )
    cat_rows = (await db.execute(cat_stmt)).all()
    by_category = {row[0]: row[1] for row in cat_rows}

    # 今日新增
    today = datetime.now(LOCAL_TZ).date()
    local_start = datetime(today.year, today.month, today.day, tzinfo=LOCAL_TZ)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    today_count = (await db.execute(
        select(func.count(CrawlerItem.id)).where(
            CrawlerItem.category.in_(active_categories),
            visible_condition,
            CrawlerItem.created_at >= utc_start,
            CrawlerItem.created_at < utc_end,
        )
    )).scalar_one() or 0

    # 各分类最新爬取时间
    latest_crawl = {}
    for cat in CATEGORIES:
        latest = (await db.execute(
            select(func.max(CrawlerItem.created_at)).where(
                CrawlerItem.category == cat,
                (CrawlerItem.relevance_score >= threshold) if cat == "bidding" else True,
            )
        )).scalar_one_or_none()
        latest_crawl[cat] = latest

    return {
        "total": total,
        "by_category": by_category,
        "today_count": today_count,
        "latest_crawl": latest_crawl,
    }


@intelligence_router.get("/categories")
async def intelligence_categories(
    _user: dict = Depends(require_permission("intelligence:view")),
) -> dict[str, Any]:
    """分类字典。"""

    return CATEGORIES


@intelligence_router.get("/analysis")
async def intelligence_analysis(
    category: str = Query("bidding", description="bidding/policy/news/competitor/ai"),
    period: str = Query("week", description="week/month"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("intelligence:view")),
) -> dict[str, Any]:
    """Agent 周/月研判。

    分析不是重新抓数据，而是基于已入库信号做聚合、过滤和动作建议。
    """

    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="unsupported category")

    start_date, end_date, bucket_mode = _period_window(period)
    stmt = (
        select(CrawlerItem)
        .where(CrawlerItem.category == category)
        .where(
            (CrawlerItem.published_at >= start_date)
            | (CrawlerItem.published_at.is_(None) & (func.date(CrawlerItem.created_at) >= start_date))
        )
        .where(
            (CrawlerItem.published_at <= end_date)
            | (CrawlerItem.published_at.is_(None) & (func.date(CrawlerItem.created_at) <= end_date))
        )
        .order_by(CrawlerItem.relevance_score.desc().nullslast(), CrawlerItem.created_at.desc())
        .limit(500)
    )
    rows = (await db.execute(stmt)).scalars().all()
    threshold = await _load_relevance_threshold(db)
    return _build_analysis(category, period, start_date, end_date, bucket_mode, rows, threshold)


@intelligence_router.get("/{item_id}")
async def intelligence_detail(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("intelligence:view")),
) -> dict[str, Any]:
    """单条资讯详情。"""

    stmt = select(CrawlerItem).where(CrawlerItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    return _crawler_item_to_dict(item)


# ---------------------------------------------------------------------------
# 爬虫管理 API
# ---------------------------------------------------------------------------


@crawler_router.get("/status")
async def crawler_status(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> list[dict[str, Any]]:
    """各爬虫运行状态。"""

    result = []
    threshold = await _load_relevance_threshold(db)
    for name, meta in CRAWLER_REGISTRY.items():
        category = meta["category"]
        count = await _count_crawler_items(db, category)
        effective_count = await _count_crawler_items(db, category, _effective_item_condition(category, threshold))
        filtered_count = max(count - effective_count, 0)

        # 最新数据入库时间
        latest_item = (await db.execute(
            select(func.max(CrawlerItem.created_at)).where(CrawlerItem.category == category)
        )).scalar_one_or_none()

        latest_run = (await db.execute(
            select(CrawlerRunLog)
            .where(CrawlerRunLog.crawler_name == name)
            .order_by(CrawlerRunLog.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        latest_task_run = (await db.execute(
            select(CrawlerTaskRun)
            .where(CrawlerTaskRun.crawler_name == name)
            .order_by(CrawlerTaskRun.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        task_lock = (await db.execute(
            select(CrawlerTaskLock).where(CrawlerTaskLock.name == name)
        )).scalar_one_or_none()

        source_details = await _configured_source_details(db, name, category)
        source_breakdown = await _source_breakdown(db, name, category)

        # 运行状态
        run_info = _crawler_run_status.get(name, {})
        locked_until = _ensure_aware_datetime(task_lock.locked_until) if task_lock and task_lock.locked_until else None
        is_locked = bool(task_lock and task_lock.lock_owner and locked_until and locked_until > datetime.now(timezone.utc))
        status = run_info.get("status") or ("running" if is_locked else (latest_run.status if latest_run else "idle"))

        result.append({
            "name": name,
            "category": category,
            "label": meta["label"],
            "total_collected": count,
            "effective_count": effective_count,
            "filtered_count": filtered_count,
            "last_run_at": latest_run.finished_at if latest_run else None,
            "last_item_at": latest_item,
            "last_run_stats": run_info.get("stats") or (_crawler_run_log_to_dict(latest_run) if latest_run else None),
            "active_sources": len(source_details),
            "source_details": source_details,
            "source_breakdown": source_breakdown,
            "strategy": _crawler_strategy(name),
            "latest_task_run": _crawler_task_run_to_dict(latest_task_run),
            "task_lock": _crawler_lock_to_dict(task_lock),
            "last_error": latest_run.error_message if latest_run else None,
            "status": status,
        })

    return result


@crawler_router.get("/runs")
async def crawler_runs(
    crawler_name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> list[dict[str, Any]]:
    """最近爬虫运行日志。"""

    stmt = select(CrawlerRunLog).order_by(CrawlerRunLog.created_at.desc()).limit(limit)
    if crawler_name:
        stmt = stmt.where(CrawlerRunLog.crawler_name == crawler_name)
    rows = (await db.execute(stmt)).scalars().all()
    return [_crawler_run_log_to_dict(row) for row in rows]


@crawler_router.post("/{crawler_name}/run")
async def run_crawler(
    crawler_name: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> CrawlRunResult:
    """手动触发单个爬虫。"""

    if crawler_name not in CRAWLER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"crawler '{crawler_name}' not found")

    results = await execute_crawlers(db, [crawler_name], trigger_source="manual")
    return results[0]


@crawler_router.post("/run-all")
async def run_all_crawlers(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> list[CrawlRunResult]:
    """手动触发全部爬虫。"""

    return await execute_crawlers(db, trigger_source="manual")


async def execute_crawlers(
    db: AsyncSession,
    crawler_names: list[str] | None = None,
    trigger_source: str = "manual",
) -> list[CrawlRunResult]:
    """Execute registered crawlers through one shared path."""

    results: list[CrawlRunResult] = []
    names = crawler_names or list(CRAWLER_REGISTRY.keys())
    for name in names:
        meta = CRAWLER_REGISTRY[name]
        lock_owner = f"{name}:{uuid.uuid4().hex[:16]}"

        if not await _acquire_crawler_task_lock(db, name, lock_owner):
            await _rollback_safely(db)
            _crawler_run_status[name] = {"status": "running", "stats": None}
            results.append(CrawlRunResult(
                crawler_name=name,
                errors=0,
                message=f"{meta['label']}正在运行，本次触发已跳过。",
            ))
            continue

        await db.commit()
        run_id: str | None = None
        _crawler_run_status[name] = {"status": "running", "stats": None}

        try:
            run_id = await _start_crawler_task_run(db, name, meta["category"], trigger_source, lock_owner)
            await db.commit()
            crawler = await _make_crawler(db, name)
            keywords = await _load_keywords(db, meta["category"], meta.get("keywords") or [])
            await _heartbeat_crawler_task(db, name, lock_owner, run_id)
            await db.commit()

            heartbeat_task = _start_crawler_heartbeat(name, lock_owner, run_id)
            try:
                stats = await crawler.run(db, keywords=keywords)
                status = _status_from_stats(stats)
                await _record_crawler_run(db, name, meta["category"], status, stats)
                await _finish_crawler_task_run(db, run_id, status, stats.to_dict(), None)
                await _release_crawler_task_lock(db, name, lock_owner)
                await db.commit()
            finally:
                await _stop_crawler_heartbeat(heartbeat_task)
            _crawler_run_status[name] = {
                "status": status,
                "stats": stats.to_dict(),
            }
            results.append(_run_result_from_stats(name, stats))
        except Exception as e:
            _crawler_run_status[name] = {"status": "error", "stats": None}
            logger.error("爬虫 %s 运行失败: %s", name, e)
            await _rollback_safely(db)
            await _record_failed_run(db, name, meta["category"], str(e))
            if run_id:
                await _finish_crawler_task_run(db, run_id, "error", None, str(e))
            await _release_crawler_task_lock(db, name, lock_owner)
            await db.commit()
            results.append(CrawlRunResult(
                crawler_name=name,
                errors=1,
                message=f"爬取失败: {str(e)}",
            ))

    return results


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _acquire_crawler_task_lock(db: AsyncSession, crawler_name: str, lock_owner: str) -> bool:
    """Acquire a DB-backed crawler lock, allowing takeover only after TTL expiry."""

    for _attempt in range(3):
        now = datetime.now(timezone.utc)
        locked_until = now + CRAWLER_TASK_LOCK_TTL
        try:
            row = (
                await db.execute(
                    select(CrawlerTaskLock)
                    .where(CrawlerTaskLock.name == crawler_name)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row and row.lock_owner:
                existing_until = _ensure_aware_datetime(row.locked_until)
                if existing_until and existing_until > now:
                    return False

            if row is None:
                row = CrawlerTaskLock(name=crawler_name)
                db.add(row)
            row.lock_owner = lock_owner
            row.locked_at = now
            row.locked_until = locked_until
            row.heartbeat_at = now
            await db.flush()
            return True
        except IntegrityError:
            await _rollback_safely(db)
            if _attempt < 2:
                await asyncio.sleep(0.1 * (_attempt + 1))
            continue
    return False


async def _release_crawler_task_lock(db: AsyncSession, crawler_name: str, lock_owner: str) -> None:
    row = (
        await db.execute(
            select(CrawlerTaskLock)
            .where(CrawlerTaskLock.name == crawler_name)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not row or row.lock_owner != lock_owner:
        return
    row.lock_owner = None
    row.locked_until = None
    row.heartbeat_at = datetime.now(timezone.utc)
    await db.flush()


async def _start_crawler_task_run(
    db: AsyncSession,
    crawler_name: str,
    category: str,
    trigger_source: str,
    lock_owner: str,
) -> str:
    now = datetime.now(timezone.utc)
    run_id = f"CTR-{crawler_name}-{uuid.uuid4().hex[:20]}"
    row = CrawlerTaskRun(
        run_id=run_id,
        crawler_name=crawler_name,
        category=category,
        trigger_source=trigger_source,
        status="running",
        lock_owner=lock_owner,
        started_at=now,
        heartbeat_at=now,
    )
    db.add(row)
    await db.flush()
    return run_id


async def _heartbeat_crawler_task(
    db: AsyncSession,
    crawler_name: str,
    lock_owner: str,
    run_id: str,
) -> None:
    now = datetime.now(timezone.utc)
    task_run = (
        await db.execute(select(CrawlerTaskRun).where(CrawlerTaskRun.run_id == run_id))
    ).scalar_one_or_none()
    if task_run:
        task_run.heartbeat_at = now
    lock = (
        await db.execute(select(CrawlerTaskLock).where(CrawlerTaskLock.name == crawler_name))
    ).scalar_one_or_none()
    if lock and lock.lock_owner == lock_owner:
        lock.heartbeat_at = now
        lock.locked_until = now + CRAWLER_TASK_LOCK_TTL
    await db.flush()


def _start_crawler_heartbeat(
    crawler_name: str,
    lock_owner: str,
    run_id: str,
) -> asyncio.Task:
    return asyncio.create_task(
        _crawler_heartbeat_loop(crawler_name, lock_owner, run_id),
        name=f"crawler-heartbeat-{crawler_name}",
    )


async def _stop_crawler_heartbeat(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


async def _crawler_heartbeat_loop(
    crawler_name: str,
    lock_owner: str,
    run_id: str,
) -> None:
    while True:
        await asyncio.sleep(CRAWLER_TASK_HEARTBEAT_INTERVAL_SECONDS)
        async with SessionLocal() as heartbeat_db:
            await _heartbeat_crawler_task(heartbeat_db, crawler_name, lock_owner, run_id)
            await heartbeat_db.commit()


async def _finish_crawler_task_run(
    db: AsyncSession,
    run_id: str,
    status: str,
    result_summary: dict[str, Any] | None,
    error_message: str | None,
) -> None:
    row = (
        await db.execute(select(CrawlerTaskRun).where(CrawlerTaskRun.run_id == run_id))
    ).scalar_one_or_none()
    if not row:
        return
    now = datetime.now(timezone.utc)
    row.status = status
    row.finished_at = now
    row.heartbeat_at = now
    row.result_summary = result_summary
    row.error_message = error_message[:1000] if error_message else None
    if row.started_at:
        started_at = _ensure_aware_datetime(row.started_at) or row.started_at
        row.duration_ms = int((now - started_at).total_seconds() * 1000)
    await db.flush()


def _visible_intelligence_condition(threshold: float = 30):
    """业务页面只展示经过相关性过滤的标讯雷达数据。"""

    return CrawlerItem.is_invalid.is_(False) & (
        (CrawlerItem.category != "bidding") | (CrawlerItem.relevance_score >= threshold)
    )


def _effective_item_condition(category: str, threshold: float = 30):
    if category == "bidding":
        return CrawlerItem.is_invalid.is_(False) & (CrawlerItem.relevance_score >= threshold)
    return CrawlerItem.is_invalid.is_(False)


async def _count_crawler_items(db: AsyncSession, category: str, condition: Any = None) -> int:
    stmt = select(func.count(CrawlerItem.id)).where(CrawlerItem.category == category)
    if condition is not None:
        stmt = stmt.where(condition)
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _source_breakdown(db: AsyncSession, crawler_name: str, category: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                CrawlerItem.source,
                func.count(CrawlerItem.id),
                func.max(CrawlerItem.created_at),
            )
            .where(CrawlerItem.category == category)
            .group_by(CrawlerItem.source)
        )
    ).all()

    merged: dict[str, dict[str, Any]] = {}
    for raw_source, count, latest in rows:
        name = _management_source_name(crawler_name, raw_source)
        current = merged.setdefault(name, {"name": name, "count": 0, "latest_item_at": None})
        current["count"] += int(count or 0)
        if latest and (current["latest_item_at"] is None or latest > current["latest_item_at"]):
            current["latest_item_at"] = latest

    result = sorted(merged.values(), key=lambda item: item["count"], reverse=True)
    for item in result:
        latest = item.get("latest_item_at")
        item["latest_item_at"] = latest.isoformat() if latest else None
    return result[:8]


def _management_source_name(crawler_name: str, raw_source: Any) -> str:
    if crawler_name == "bidding":
        source = str(raw_source or "")
        if source in {"标讯数据", "结构化标讯数据", "结构化标讯接口"}:
            return "结构化标讯接口"
        return source or "未标注来源"
    return str(raw_source or "未标注来源")


async def _configured_source_details(db: AsyncSession, crawler_name: str, category: str) -> list[dict[str, Any]]:
    if crawler_name == "bidding":
        primary_policy = normalize_crawl_policy({"risk_level": "authorized_api"}, source_type="api", category="bidding")
        primary_strategy = build_source_strategy_profile({
            "category": "bidding",
            "name": "结构化标讯接口",
            "selectors": {
                "type": "api",
                "protected": True,
                "risk_level": "authorized_api",
                "scope": "招标公告、中标结果、成交结果、采购意向等结构化标讯",
                "strategy": "按管理后台关键词检索，入库后再做业务相关性评分与金额抽取",
            },
            "is_active": True,
        })
        sources = [{
            "name": "结构化标讯接口",
            "type": "api",
            "url": None,
            "base_url": None,
            "is_active": True,
            "capability_status": "ready",
            "capability_reason": "当前标讯主链路，已接入运行链路",
            "scope": "招标公告、中标结果、成交结果、采购意向等结构化标讯",
            "strategy": "按管理后台关键词检索，入库后再做业务相关性评分与金额抽取",
            "crawl_policy": primary_policy,
            "risk_level": primary_policy.get("risk_level"),
            "anti_crawl_strategy": policy_summary(primary_policy),
            "source_tier": primary_strategy["source_tier"],
            "strategy_status": primary_strategy["strategy_status"],
            "strategy_status_label": primary_strategy["strategy_status_label"],
            "strategy_gaps": primary_strategy["strategy_gaps"],
            "strategy_sort_rank": primary_strategy["strategy_sort_rank"],
            "collection_strategy": primary_strategy["collection_strategy"],
            "anti_crawl_plan": primary_strategy["anti_crawl_plan"],
            "strategy_steps": primary_strategy["strategy_steps"],
            "stop_rules": primary_strategy["stop_rules"],
            "operator_action": primary_strategy["operator_action"],
            "rule_profile": "authorized_api_v1",
            "rule_status": "executable",
            "rule_note": "已授权结构化接口，按管理后台关键词分页检索。",
        }]
        for source in await _active_sources(db, category, include_protected=False):
            selectors = source.get("selectors") or {}
            if selectors.get("protected"):
                continue
            sources.append(_source_detail(source, category=category))
        return sources

    crawler = CRAWLER_REGISTRY[crawler_name]["class"]()
    default_sources = list(getattr(crawler, "sources", []) or [])
    db_sources = await _active_sources(db, category, include_protected=True)
    return [_source_detail(source, category=category) for source in (db_sources or default_sources)]


def _source_detail(source: dict[str, Any], *, category: str | None = None) -> dict[str, Any]:
    selectors = source.get("selectors") or {}
    source_type = source.get("type") or selectors.get("type") or "html"
    crawl_policy = source.get("crawl_policy") or normalize_crawl_policy(selectors, source_type=source_type, category=category)
    strategy_profile = build_source_strategy_profile({
        "category": source.get("category") or category,
        "name": source.get("name"),
        "url": source.get("url"),
        "base_url": source.get("base_url"),
        "selectors": selectors,
        "is_active": source.get("is_active", True),
    })
    return {
        "name": source.get("name") or source.get("url") or "未命名来源",
        "type": source_type,
        "url": source.get("url"),
        "base_url": source.get("base_url"),
        "is_active": True,
        "capability_status": "ready",
        "capability_reason": "已接入当前采集运行链路",
        "scope": selectors.get("scope") or _source_scope(source_type),
        "strategy": selectors.get("strategy") or _source_strategy(source_type),
        "risk_level": crawl_policy.get("risk_level"),
        "crawl_policy": crawl_policy,
        "anti_crawl_strategy": policy_summary(crawl_policy),
        "source_tier": strategy_profile["source_tier"],
        "strategy_status": strategy_profile["strategy_status"],
        "strategy_status_label": strategy_profile["strategy_status_label"],
        "strategy_gaps": strategy_profile["strategy_gaps"],
        "strategy_sort_rank": strategy_profile["strategy_sort_rank"],
        "collection_strategy": strategy_profile["collection_strategy"],
        "anti_crawl_plan": strategy_profile["anti_crawl_plan"],
        "strategy_steps": strategy_profile["strategy_steps"],
        "stop_rules": strategy_profile["stop_rules"],
        "operator_action": strategy_profile["operator_action"],
        "rule_profile": selectors.get("rule_profile"),
        "rule_status": selectors.get("rule_status"),
        "rule_note": selectors.get("rule_note") or selectors.get("execution_note"),
    }


def _source_scope(source_type: str) -> str:
    if source_type == "api":
        return "结构化接口数据"
    if source_type == "rss":
        return "RSS/订阅源更新"
    if source_type == "browser":
        return "需要渲染的公开网页"
    return "公开网页列表与详情页"


def _source_strategy(source_type: str) -> str:
    if source_type == "api":
        return "接口分页拉取，控制请求频率，按返回字段结构化入库"
    if source_type == "rss":
        return "订阅增量解析，按发布时间去重"
    if source_type == "browser":
        return "低频渲染采集，限制并发，失败后退避重试"
    return "静态页面低频采集，遵守 robots 与限速，列表去重后读取详情"


def _crawler_strategy(crawler_name: str) -> dict[str, Any]:
    strategies = {
        "bidding": {
            "source_type": "授权结构化接口",
            "fetch_method": "按关键词组合检索，分页拉取公告数据",
            "anti_crawl": "接口限速、失败退避、去重入库；不对无关政府站做泛抓取",
            "filter_policy": "先按业务关键词召回，再按管理中心阈值过滤，低分数据只留采集日志不进业务视图",
            "business_scope": "公安、政数、自然资源、时空大数据、地址治理、地图/空间智能、Agent 相关项目",
        },
        "policy": {
            "source_type": "公开政策网站",
            "fetch_method": "按年度与关键词采集政策标题、摘要、正文链接",
            "anti_crawl": "低频请求、User-Agent 标识、失败退避、尊重 robots，不做高并发扫描",
            "filter_policy": "只保留与公安、政数、大数据、电力、运营商、地址/地图/空间/Agent 相关政策",
            "business_scope": "政策导向、预算方向、行业监管与数字化建设机会",
        },
        "market": {
            "source_type": "公开市场信息源",
            "fetch_method": "按行业关键词抓取新闻、动态、公开线索",
            "anti_crawl": "低频采集、来源去重、异常熔断",
            "filter_policy": "排除泛新闻，只保留与目标行业和能力关键词相关的市场变化",
            "business_scope": "客户建设动态、行业事件、市场趋势和潜在线索",
        },
        "competitor": {
            "source_type": "公开网页/新闻/案例",
            "fetch_method": "围绕竞对名称、产品、客户案例和中标事件做定向监控",
            "anti_crawl": "低频抓取、来源白名单、失败退避",
            "filter_policy": "按竞对、客户、区域、产品动作分类，仅推送中高影响事件",
            "business_scope": "竞对中标、重点客户案例、产品发布、区域动作",
        },
        "ai": {
            "source_type": "行业知识源",
            "fetch_method": "定向采集 AI Agent、空间数据、GIS、地址治理和数据治理相关行业内容",
            "anti_crawl": "订阅优先、低频网页采集、来源去重",
            "filter_policy": "排除泛科技内容，沉淀对产品、售前和方案有用的知识素材",
            "business_scope": "Agent Native、空间数据/GIS、地址治理、时空智能、行业技术趋势和解决方案素材",
        },
    }
    return strategies.get(crawler_name, {
        "source_type": "公开数据源",
        "fetch_method": "按配置来源采集",
        "anti_crawl": "低频请求、失败退避、来源去重",
        "filter_policy": "按关键词和相关性过滤",
        "business_scope": "业务相关市场信号",
    })


async def _make_crawler(db: AsyncSession, crawler_name: str) -> BaseCrawler:
    """创建爬虫实例，并合并管理中心配置的启用来源。"""

    meta = CRAWLER_REGISTRY[crawler_name]
    crawler: BaseCrawler = meta["class"]()
    if crawler_name == "bidding":
        db_sources = await _active_sources(db, meta["category"], include_protected=False)
        if db_sources and hasattr(crawler, "sources"):
            setattr(crawler, "sources", db_sources)
        return crawler

    db_sources = await _active_sources(db, meta["category"], include_protected=True)
    if db_sources and hasattr(crawler, "sources"):
        setattr(crawler, "sources", db_sources)
    return crawler


async def _active_sources(
    db: AsyncSession,
    category: str,
    *,
    include_protected: bool = True,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(CrawlerSource)
        .where(CrawlerSource.category == category, CrawlerSource.is_active.is_(True))
        .order_by(CrawlerSource.id)
    )).scalars().all()

    sources: list[dict[str, Any]] = []
    for row in rows:
        selectors = row.selectors or {}
        if selectors.get("protected") and not include_protected:
            continue
        if _source_is_in_cooldown(row, now):
            continue
        if not _runtime_source_ready(row.category, selectors):
            continue
        source_type = selectors.get("type") or selectors.get("source_type")
        runtime_keys = {
            "type",
            "source_type",
            "scope",
            "strategy",
            "protected",
            "risk_level",
            "crawl_policy",
            "access_level",
            "min_interval_seconds",
            "max_requests_per_minute",
            "respect_robots",
            "use_conditional_request",
            "discover_feeds",
            "requires_browser",
            "fallback_action",
            "pages",
            "payload",
            "headers",
            "records_path",
            "query_keywords",
        }
        cleaned_selectors = {k: v for k, v in selectors.items() if k not in runtime_keys}
        crawl_policy = normalize_crawl_policy(selectors, source_type=source_type, category=row.category)
        item: dict[str, Any] = {
            "source_id": row.id,
            "name": row.name,
            "url": row.url,
            "base_url": row.base_url,
            "selectors": cleaned_selectors,
            "crawl_policy": crawl_policy,
        }
        if source_type:
            item["type"] = source_type
        for runtime_key in ("pages", "payload", "headers", "records_path", "query_keywords"):
            if runtime_key in selectors:
                item[runtime_key] = selectors[runtime_key]
        sources.append(item)
    return sources


def _source_is_in_cooldown(row: CrawlerSource, now: datetime | None = None) -> bool:
    cooldown_until = _ensure_aware_datetime(row.cooldown_until)
    if cooldown_until is None:
        return False
    return cooldown_until > (now or datetime.now(timezone.utc))


async def _active_source_count(db: AsyncSession, category: str) -> int:
    return (await db.execute(
        select(func.count(CrawlerSource.id)).where(
            CrawlerSource.category == category,
            CrawlerSource.is_active.is_(True),
        )
    )).scalar_one() or 0


async def _configured_source_count(db: AsyncSession, crawler_name: str, category: str) -> int:
    if crawler_name == "bidding":
        return 1 + len(await _active_sources(db, category, include_protected=False))
    crawler = CRAWLER_REGISTRY[crawler_name]["class"]()
    default_sources = list(getattr(crawler, "sources", []) or [])
    db_sources = await _active_sources(db, category, include_protected=True)
    return len(db_sources or default_sources)


def _merge_sources(default_sources: list[dict[str, Any]], db_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in [*default_sources, *db_sources]:
        key = source.get("url") or source.get("name") or str(source)
        if key in seen:
            continue
        seen.add(key)
        merged.append(source)
    return merged


def _normalize_intelligence_sort_by(sort_by: str | None) -> str:
    value = str(sort_by or "").strip().lower()
    aliases = {
        "date": "published_at",
        "published": "published_at",
        "publish_date": "published_at",
        "score": "relevance",
        "relevance_score": "relevance",
        "amount_wan": "amount",
        "amount_display": "amount",
        "created": "created_at",
    }
    value = aliases.get(value, value)
    if value not in {"published_at", "amount", "relevance", "created_at"}:
        return "published_at"
    return value


def _intelligence_order_by(sort_by: str, sort_order: str) -> tuple[Any, ...]:
    descending = sort_order != "asc"
    column_map = {
        "published_at": CrawlerItem.published_at,
        "amount": CrawlerItem.amount_wan,
        "relevance": CrawlerItem.relevance_score,
        "created_at": CrawlerItem.created_at,
    }
    column = column_map.get(sort_by, CrawlerItem.published_at)
    primary = column.desc().nullslast() if descending else column.asc().nullslast()
    if sort_by == "published_at":
        return (primary, CrawlerItem.created_at.desc(), CrawlerItem.id.desc())
    if sort_by == "relevance":
        return (primary, CrawlerItem.published_at.desc().nullslast(), CrawlerItem.created_at.desc())
    return (primary, CrawlerItem.id.desc())


def _sort_items_by_amount(rows: list[CrawlerItem], sort_order: str) -> list[CrawlerItem]:
    if sort_order == "asc":
        return sorted(
            rows,
            key=lambda row: (
                _item_amount_wan(row) <= 0,
                _item_amount_wan(row) if _item_amount_wan(row) > 0 else float("inf"),
                row.published_at or date.max,
                row.created_at or datetime.max.replace(tzinfo=timezone.utc),
            ),
        )
    return sorted(
        rows,
        key=lambda row: (
            _item_amount_wan(row),
            row.published_at or date.min,
            row.created_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )


async def _load_keywords(db: AsyncSession, category: str, fallback: list[str]) -> list[str]:
    row = (await db.execute(
        select(KeywordConfig).where(KeywordConfig.category == category)
    )).scalar_one_or_none()
    if row and row.keywords:
        return row.keywords
    return fallback


async def _load_relevance_threshold(db: AsyncSession) -> float:
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    if not row:
        return 30.0
    return float(row.relevance_threshold)


def _runtime_source_ready(category: str, selectors: dict[str, Any]) -> bool:
    source_type = selectors.get("type") or selectors.get("source_type") or "official_site"
    if category == "bidding":
        if source_type in {"api", "browser"}:
            return False
        if source_type == "direct_pages":
            return bool(selectors.get("pages"))
        return bool(selectors.get("list") and selectors.get("title"))
    if source_type == "browser":
        return False
    if source_type == "rss":
        return category == "ai"
    if source_type == "direct_pages":
        return bool(selectors.get("pages"))
    if source_type == "api_post":
        return bool(selectors.get("payload") is not None and selectors.get("records_path"))
    if source_type == "api":
        return False
    return bool(selectors.get("list") and selectors.get("title"))


def _status_from_stats(stats: CrawlStats) -> str:
    if stats.errors <= 0:
        return "completed"
    if stats.total_found > 0 or stats.new_saved > 0 or stats.duplicates_skipped > 0:
        return "partial"
    return "error"


async def _record_crawler_run(
    db: AsyncSession,
    crawler_name: str,
    category: str,
    status: str,
    stats: CrawlStats,
) -> CrawlerRunLog:
    error_message = "; ".join(stats.error_messages[:3]) if stats.error_messages else None
    diagnostics = build_crawler_run_diagnostics(
        crawler_name=crawler_name,
        category=category,
        stats=stats,
    )
    await _update_crawler_source_health(db, category, diagnostics.get("source_reports") or [])
    row = CrawlerRunLog(
        crawler_name=crawler_name,
        category=category,
        status=status,
        total_found=stats.total_found,
        new_saved=stats.new_saved,
        duplicates_skipped=stats.duplicates_skipped,
        low_score_discarded=stats.low_score_discarded,
        errors=stats.errors,
        error_message=error_message[:1000] if error_message else None,
        started_at=stats.started_at,
        finished_at=stats.finished_at,
        duration_ms=stats.duration_ms,
        extra_data={
            **diagnostics,
            "error_messages": stats.error_messages[:10],
            "raw_by_source": stats.raw_by_source,
            "saved_by_source": stats.saved_by_source,
            "duplicate_by_source": stats.duplicate_by_source,
            "discarded_by_source": stats.discarded_by_source,
            "latest_by_source": stats.latest_by_source,
        },
    )
    db.add(row)
    await db.flush()
    return row


async def _update_crawler_source_health(
    db: AsyncSession,
    category: str,
    source_reports: list[dict[str, Any]],
) -> None:
    """Persist per-source health so operators can manage crawler sources."""

    if not source_reports:
        return

    rows = (await db.execute(select(CrawlerSource).where(CrawlerSource.category == category))).scalars().all()
    if not rows:
        return

    now = datetime.now(timezone.utc)
    by_id = {row.id: row for row in rows}
    by_name = {str(row.name or "").strip(): row for row in rows if row.name}
    by_url = {str(row.url or "").strip(): row for row in rows if row.url}
    protected_rows = [
        row for row in rows
        if (row.selectors or {}).get("protected")
    ]

    for report in source_reports:
        row = _match_crawler_source_report(report, by_id, by_name, by_url, protected_rows)
        if row is None:
            continue

        diagnosis_code = str(report.get("diagnosis_code") or report.get("status") or "unknown")
        diagnosis_label = str(report.get("diagnosis_label") or report.get("status_label") or diagnosis_code)
        runtime_status = _runtime_status_from_diagnosis(diagnosis_code, report)
        failed = runtime_status in {"blocked", "error", "skipped"}
        previous_failures = int(row.consecutive_failures or 0)
        failures = previous_failures + 1 if failed else 0

        row.runtime_status = runtime_status
        row.consecutive_failures = failures
        row.last_checked_at = now
        row.last_diagnosis_code = diagnosis_code[:80]
        row.last_diagnosis_label = diagnosis_label[:120]
        row.last_found = int(report.get("raw_count") or report.get("found") or 0)
        row.last_saved = int(report.get("saved_count") or 0)
        if report.get("latest_item"):
            row.last_cursor = report.get("latest_item")

        if failed:
            row.last_error_at = now
            row.last_error_message = str(report.get("error") or report.get("next_action") or diagnosis_label)[:1000]
            row.cooldown_until = _cooldown_until(diagnosis_code, failures, now)
        else:
            row.last_success_at = now
            row.last_error_message = None
            row.cooldown_until = None


def _match_crawler_source_report(
    report: dict[str, Any],
    by_id: dict[int, CrawlerSource],
    by_name: dict[str, CrawlerSource],
    by_url: dict[str, CrawlerSource],
    protected_rows: list[CrawlerSource],
) -> CrawlerSource | None:
    source_id = report.get("source_id")
    if source_id is not None:
        try:
            row = by_id.get(int(source_id))
            if row is not None:
                return row
        except (TypeError, ValueError):
            pass

    name = str(report.get("name") or "").strip()
    url = str(report.get("url") or "").strip()
    if name in by_name:
        return by_name[name]
    if url in by_url:
        return by_url[url]
    if name in {"结构化标讯数据", "结构化标讯接口", "标讯数据"} and protected_rows:
        return protected_rows[0]
    return None


def _runtime_status_from_diagnosis(diagnosis_code: str, report: dict[str, Any]) -> str:
    if diagnosis_code == "ok":
        return "healthy"
    if diagnosis_code == "no_match":
        return "empty"
    if diagnosis_code in {"robots_blocked", "challenge_detected", "rate_limited", "forbidden"}:
        return "blocked"
    if diagnosis_code in {"missing_config", "skipped"} or report.get("status") == "skipped":
        return "skipped"
    if report.get("status") == "ok":
        return "healthy"
    return "error"


def _cooldown_until(diagnosis_code: str, failures: int, now: datetime) -> datetime | None:
    if diagnosis_code == "robots_blocked":
        return now + timedelta(days=7)
    if diagnosis_code in {"challenge_detected", "forbidden"}:
        return now + timedelta(days=1)
    if diagnosis_code == "rate_limited":
        return now + timedelta(hours=6)
    if diagnosis_code in {"missing_config", "skipped"}:
        return None
    if failures >= 5:
        return now + timedelta(hours=12)
    if failures >= 3:
        return now + timedelta(hours=3)
    return None


async def _record_failed_run(
    db: AsyncSession,
    crawler_name: str,
    category: str,
    error_message: str,
) -> None:
    now = datetime.now(timezone.utc)
    db.add(CrawlerRunLog(
        crawler_name=crawler_name,
        category=category,
        status="error",
        errors=1,
        error_message=error_message[:1000],
        started_at=now,
        finished_at=now,
        duration_ms=0,
        extra_data={"error_messages": [error_message]},
    ))
    await db.flush()


async def _rollback_safely(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception as rollback_error:  # noqa: BLE001
        logger.warning("rollback failed after crawler error: %s", rollback_error)


def _run_result_from_stats(crawler_name: str, stats: CrawlStats) -> CrawlRunResult:
    if stats.errors:
        message = (
            f"采集完成但有异常：发现 {stats.total_found} 条，新增 {stats.new_saved} 条，"
            f"重复 {stats.duplicates_skipped} 条，低相关丢弃 {stats.low_score_discarded} 条，错误 {stats.errors} 个"
        )
    else:
        message = (
            f"采集完成：发现 {stats.total_found} 条，新增 {stats.new_saved} 条，"
            f"重复 {stats.duplicates_skipped} 条，低相关丢弃 {stats.low_score_discarded} 条"
        )
    return CrawlRunResult(
        crawler_name=crawler_name,
        total_found=stats.total_found,
        new_saved=stats.new_saved,
        duplicates_skipped=stats.duplicates_skipped,
        low_score_discarded=stats.low_score_discarded,
        errors=stats.errors,
        duration_ms=stats.duration_ms,
        message=message,
    )


def _crawler_run_log_to_dict(row: CrawlerRunLog | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "crawler_name": row.crawler_name,
        "category": row.category,
        "status": row.status,
        "total_found": row.total_found,
        "new_saved": row.new_saved,
        "duplicates_skipped": row.duplicates_skipped,
        "low_score_discarded": row.low_score_discarded,
        "errors": row.errors,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
        "extra_data": _public_run_extra(row),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _crawler_task_run_to_dict(row: CrawlerTaskRun | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "run_id": row.run_id,
        "crawler_name": row.crawler_name,
        "category": row.category,
        "trigger_source": row.trigger_source,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
        "duration_ms": row.duration_ms,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _crawler_lock_to_dict(row: CrawlerTaskLock | None) -> dict[str, Any] | None:
    if row is None:
        return None
    locked_until = _ensure_aware_datetime(row.locked_until)
    return {
        "name": row.name,
        "is_locked": bool(row.lock_owner and locked_until and locked_until > datetime.now(timezone.utc)),
        "locked_at": row.locked_at.isoformat() if row.locked_at else None,
        "locked_until": row.locked_until.isoformat() if row.locked_until else None,
        "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
    }


def _ensure_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _period_window(period: str) -> tuple[date, date, str]:
    today = datetime.now(LOCAL_TZ).date()
    if period == "month":
        start = today.replace(day=1)
        return start, today, "week"
    start = today - timedelta(days=today.weekday())
    return start, today, "day"


def _build_analysis(
    category: str,
    period: str,
    start_date: date,
    end_date: date,
    bucket_mode: str,
    rows: list[CrawlerItem],
    relevance_threshold: float = 30.0,
) -> dict[str, Any]:
    relevant_rows = [row for row in rows if float(row.relevance_score or 0) >= relevance_threshold]
    ignored_rows = len(rows) - len(relevant_rows)
    score_values = [float(row.relevance_score or 0) for row in relevant_rows]

    topic_counter: Counter[str] = Counter()
    customer_counter: Counter[str] = Counter()
    region_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    keyword_counter: Counter[str] = Counter()
    notice_type_counter: Counter[str] = Counter()
    bucket_counter: Counter[str] = Counter()
    amount_total = 0.0

    for row in relevant_rows:
        extra = row.extra_data or {}
        profile = extra.get("agent_profile") or {}
        for topic in profile.get("topics") or []:
            topic_counter[str(topic)] += 1
        for customer_type in profile.get("customer_types") or []:
            customer_counter[str(customer_type)] += 1
        if profile.get("recommended_action"):
            action_counter[str(profile["recommended_action"])] += 1
        location = _item_region(row)
        if location:
            region_counter[location] += 1
        for keyword in _item_matched_keywords(row):
            keyword_counter[keyword] += 1
        notice_type = _item_notice_type(row) if row.category == "bidding" else ""
        if notice_type:
            notice_type_counter[notice_type] += 1
        amount_total += _item_amount_wan(row)
        bucket_counter[_bucket_key(row, bucket_mode)] += 1

    top_items = [_analysis_item(row) for row in relevant_rows[:8]]
    evidence_records = [_analysis_evidence_record(row) for row in relevant_rows[:12]]
    label = _analysis_label(category)
    findings = _analysis_findings(label, relevant_rows, ignored_rows, topic_counter, customer_counter, amount_total)
    recommendations = _analysis_recommendations(category, relevant_rows, topic_counter, customer_counter)

    return {
        "category": category,
        "label": label,
        "period": period,
        "range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "summary": {
            "total": len(rows),
            "relevant": len(relevant_rows),
            "ignored": ignored_rows,
            "avg_score": round(sum(score_values) / len(score_values), 1) if score_values else 0,
            "amount_total_wan": round(amount_total, 1),
            "relevance_threshold": round(relevance_threshold, 1),
            "evidence_count": len(evidence_records),
        },
        "distribution": {
            "topics": _counter_items(topic_counter),
            "customer_types": _counter_items(customer_counter),
            "regions": _counter_items(region_counter),
            "actions": _counter_items(action_counter),
            "keywords": _counter_items(keyword_counter),
            "notice_types": _counter_items(notice_type_counter),
            "timeline": [{"label": key, "count": bucket_counter[key]} for key in sorted(bucket_counter)],
        },
        "findings": findings,
        "recommendations": recommendations,
        "top_items": top_items,
        "evidence_records": evidence_records,
    }


def _analysis_label(category: str) -> str:
    return {
        "bidding": "标讯雷达",
        "policy": "政策研判",
        "news": "市场线索",
        "competitor": "竞对监控",
        "ai": "行业知识",
    }.get(category, category)


def _analysis_findings(
    label: str,
    relevant_rows: list[CrawlerItem],
    ignored_rows: int,
    topic_counter: Counter[str],
    customer_counter: Counter[str],
    amount_total: float,
) -> list[str]:
    if not relevant_rows:
        return [f"本周期{label}没有形成可行动信号，建议检查关键词配置和数据源命中情况。"]

    findings = [f"本周期形成 {len(relevant_rows)} 条有效信号，过滤 {ignored_rows} 条低相关噪音。"]
    if topic_counter:
        topic, count = topic_counter.most_common(1)[0]
        findings.append(f"最集中主题是「{topic}」，共 {count} 条，适合作为本周期研判主线。")
    if customer_counter:
        customer, count = customer_counter.most_common(1)[0]
        findings.append(f"客户类型以「{customer}」为主，共 {count} 条，应优先匹配对应解决方案。")
    if amount_total > 0:
        findings.append(f"可识别金额合计约 {amount_total:.1f} 万元，用于判断本周期机会池规模。")
    return findings[:4]


def _analysis_recommendations(
    category: str,
    relevant_rows: list[CrawlerItem],
    topic_counter: Counter[str],
    customer_counter: Counter[str],
) -> list[str]:
    if not relevant_rows:
        return ["先调整关键词和采集规则，再运行 Agent 复核。"]
    if category == "bidding":
        actions = [
            "按评分从高到低做人工确认，只把确认后的项目转入商机中心。",
            "对高频主题生成一页售前话术，避免销售只看到公告原文。",
            "每周复盘被过滤标讯，补充排除词，持续压低无关采购噪音。",
        ]
    elif category == "policy":
        actions = [
            "把高影响政策拆成客户场景、预算来源和可售能力三类解读。",
            "将政策窗口同步给销售，但不直接生成商机。",
        ]
    elif category == "competitor":
        actions = [
            "对竞对中标和案例做区域归因，提示销售调整打法。",
            "只推送中高影响事件，普通新闻归档为背景知识。",
        ]
    else:
        actions = [
            "沉淀为售前素材和行业话术，不直接进入销售推进。",
            "对重复主题做周度摘要，减少销售阅读负担。",
        ]
    if topic_counter:
        actions.insert(0, f"围绕「{topic_counter.most_common(1)[0][0]}」形成本周期重点研判。")
    if customer_counter:
        actions.insert(1, f"优先匹配「{customer_counter.most_common(1)[0][0]}」客户打法。")
    return actions[:5]


def _analysis_item(row: CrawlerItem) -> dict[str, Any]:
    extra = row.extra_data or {}
    profile = extra.get("agent_profile") or {}
    return {
        "evidence_id": _analysis_evidence_id(row),
        "id": row.id,
        "title": row.title,
        "score": round(float(row.relevance_score or 0), 1),
        "source": _public_source_name(row),
        "source_url": row.source_url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "topics": profile.get("topics") or [],
        "customer_types": profile.get("customer_types") or [],
        "recommended_action": profile.get("recommended_action"),
        "amount_wan": round(_item_amount_wan(row), 2),
        "matched_keywords": _item_matched_keywords(row)[:8],
        "buyer": row.buyer or str(extra.get("buyer") or "").strip() or None,
        "region": _item_region(row),
        "notice_type": _item_notice_type(row) if row.category == "bidding" else None,
        "location": _item_region(row),
        "summary": _public_summary(row),
    }


def _analysis_evidence_record(row: CrawlerItem) -> dict[str, Any]:
    extra = row.extra_data or {}
    return {
        "evidence_id": _analysis_evidence_id(row),
        "record_id": row.id,
        "category": row.category,
        "title": row.title,
        "source": _public_source_name(row),
        "source_url": row.source_url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "score": round(float(row.relevance_score or 0), 1),
        "amount_wan": round(_item_amount_wan(row), 2),
        "buyer": row.buyer or str(extra.get("buyer") or "").strip() or None,
        "region": _item_region(row),
        "notice_type": _item_notice_type(row) if row.category == "bidding" else None,
        "matched_keywords": _item_matched_keywords(row)[:8],
        "summary": _public_summary(row),
    }


def _analysis_evidence_id(row: CrawlerItem) -> str:
    return f"EV-{row.category.upper()}-{row.id}"


def _bucket_key(row: CrawlerItem, bucket_mode: str) -> str:
    day = row.published_at or (row.created_at.date() if row.created_at else datetime.now(LOCAL_TZ).date())
    if bucket_mode == "week":
        start = day - timedelta(days=day.weekday())
        return f"{start.month:02d}/{start.day:02d}"
    return f"{day.month:02d}/{day.day:02d}"


def _counter_items(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _parse_amount_to_wan(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    if "亿" in text:
        return amount * 10000
    if "元" in text and "万元" not in text and "万" not in text:
        return amount / 10000
    return amount


def _item_amount_wan(item: CrawlerItem) -> float:
    if item.amount_wan and item.amount_wan > 0:
        return float(item.amount_wan)
    extra = item.extra_data or {}
    for key in ("amount_wan", "bid_amount"):
        amount = _parse_amount_to_wan(extra.get(key))
        if amount > 0:
            return amount
    amount = _parse_labeled_amount_to_wan(" ".join([item.summary or "", item.content or "", item.title or ""]))
    return amount


def _item_region(item: CrawlerItem) -> str | None:
    if item.region:
        return str(item.region).strip("- ") or None
    extra = item.extra_data or {}
    location = str(extra.get("location") or extra.get("region") or extra.get("area") or "").strip("- ")
    return location or None


def _item_notice_type(item: CrawlerItem) -> str:
    if item.notice_type:
        return item.notice_type
    return _notice_type(item.extra_data or {})


def _item_matched_keywords(item: CrawlerItem) -> list[str]:
    raw = item.matched_keywords
    if raw:
        values = raw if isinstance(raw, list) else [raw]
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            keyword = str(value or "").strip()
            if not keyword or len(keyword) > 24:
                continue
            key = keyword.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(keyword)
        if result:
            return result
    return _matched_keywords(item.extra_data or {})


def _parse_labeled_amount_to_wan(text: str) -> float:
    cleaned = re.sub(r"\s+", "", str(text or "").replace(",", ""))
    if not cleaned:
        return 0.0
    patterns = [
        r"(?:预算金额|预算价|项目预算|采购预算|最高限价|控制价|招标控制价|中标金额|成交金额|中标价|成交价|报价金额|合同金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
        r"(?:人民币|金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        amount = _parse_amount_to_wan("".join(match.groups()))
        if amount > 0:
            return amount
    return 0.0


def _matched_keywords(extra: dict[str, Any]) -> list[str]:
    raw_values = [
        extra.get("matched_keywords"),
        extra.get("keywords"),
        extra.get("query_keyword"),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not raw:
            continue
        if isinstance(raw, list):
            parts = [str(part).strip() for part in raw]
        else:
            parts = [part.strip() for part in re.split(r"[,，、\s]+", str(raw)) if part.strip()]
        for part in parts:
            if len(part) > 24:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(part)
    return result


def _public_source_name(item: CrawlerItem) -> str:
    if item.category == "bidding":
        return "标讯数据"
    return item.source or "外部信号"


def _public_summary(item: CrawlerItem) -> str | None:
    if item.category != "bidding":
        return item.summary

    extra = item.extra_data or {}
    parts = []
    buyer = str(item.buyer or extra.get("buyer") or "").strip()
    winner = str(extra.get("winner") or "").strip()
    amount_wan = _item_amount_wan(item)
    notice_type = _item_notice_type(item)
    if buyer:
        parts.append(f"采购人: {buyer}")
    if winner:
        parts.append(f"中标: {winner}")
    if amount_wan > 0:
        parts.append(f"金额: {_format_amount_wan(amount_wan)}")
    if notice_type:
        parts.append(f"类型: {notice_type}")
    return " | ".join(parts) if parts else item.summary


def _notice_type(extra: dict[str, Any]) -> str:
    text = " ".join(str(extra.get(key) or "") for key in ("subtype", "channel", "basic_class"))
    patterns = [
        "公开招标",
        "招标公告",
        "竞争性磋商",
        "询价",
        "单一来源",
        "采购意向",
        "更正公告",
        "中标结果",
        "成交结果",
        "候选人公示",
        "调研公告",
        "废标",
        "流标",
    ]
    for pattern in patterns:
        if pattern in text:
            return pattern
    if "中标" in text:
        return "中标结果"
    if "成交" in text:
        return "成交结果"
    if "招标" in text:
        return "招标公告"
    if "公示" in text:
        return "公示"
    return "公告"


def _format_amount_wan(amount: float) -> str:
    if amount >= 10000:
        return f"{amount / 10000:.2f}亿元"
    if amount >= 100:
        return f"{amount:.1f}万元"
    return f"{amount:.2f}万元"


def _public_run_extra(row: CrawlerRunLog) -> dict[str, Any] | None:
    extra = dict(row.extra_data or {})
    if row.category != "bidding":
        return extra or None

    sanitized_reports = []
    for report in extra.get("source_reports") or []:
        if not isinstance(report, dict):
            continue
        report_url = str(report.get("url") or "")
        report_name = str(report.get("name") or "")
        is_authorized_source = "结构化标讯" in report_name or "结构化标讯" in str(report.get("diagnosis_label") or "") or "jianyu360.com" in report_url
        sanitized = {
            "source_id": report.get("source_id"),
            "name": "结构化标讯接口" if is_authorized_source else (report.get("name") or "公开标讯源"),
            "status": report.get("status"),
            "status_label": report.get("status_label"),
            "found": report.get("found", 0),
            "query_keywords": report.get("query_keywords") or [],
            "source_type": "authorized_api" if is_authorized_source else report.get("source_type"),
            "diagnosis_code": report.get("diagnosis_code"),
            "diagnosis_label": report.get("diagnosis_label"),
            "severity": report.get("severity"),
            "next_action": report.get("next_action"),
            "anti_crawl_level": report.get("anti_crawl_level"),
            "compliance": report.get("compliance"),
            "raw_count": report.get("raw_count", 0),
            "saved_count": report.get("saved_count", 0),
            "duplicate_count": report.get("duplicate_count", 0),
            "discarded_count": report.get("discarded_count", 0),
        }
        if report.get("error"):
            sanitized["error"] = report.get("error")
        sanitized_reports.append(sanitized)
    extra["source_reports"] = sanitized_reports
    return extra


def _crawler_item_to_dict(item: CrawlerItem) -> dict[str, Any]:
    """序列化 CrawlerItem ORM 对象。"""

    extra_data = dict(item.extra_data or {})
    amount_wan = _item_amount_wan(item)
    amount_display = _format_amount_wan(amount_wan) if amount_wan > 0 else None
    matched_keywords = _item_matched_keywords(item)
    region = _item_region(item)
    notice_type = _item_notice_type(item) if item.category == "bidding" else item.notice_type
    if amount_wan > 0:
        extra_data["amount_wan"] = round(amount_wan, 4)
        extra_data["amount_display"] = amount_display
    if item.buyer:
        extra_data["buyer"] = item.buyer
    if region:
        extra_data["location"] = region
    if notice_type:
        extra_data["notice_type"] = notice_type
    if matched_keywords:
        extra_data["matched_keywords"] = matched_keywords

    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "summary": _public_summary(item),
        "source": _public_source_name(item),
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": item.relevance_score,
        "amount_wan": round(amount_wan, 4) if amount_wan > 0 else None,
        "amount_display": amount_display,
        "buyer": item.buyer,
        "region": region,
        "notice_type": notice_type,
        "matched_keywords": matched_keywords or None,
        "extra_data": extra_data or None,
        "is_pushed": item.is_pushed,
        "is_invalid": item.is_invalid,
        "invalid_reason": item.invalid_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


# ---------------------------------------------------------------------------
# 爬虫数据管理：归档 & 标记
# ---------------------------------------------------------------------------


@crawler_router.delete("/items/{item_id}")
async def delete_crawler_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawlers")),
) -> dict[str, Any]:
    """归档单条爬虫数据。

    这里保留 DELETE 路径以兼容旧前端/脚本，但实际执行软删除，
    避免市场情报证据链被物理删除打断。
    """
    item = (await db.execute(select(CrawlerItem).where(CrawlerItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="数据不存在")
    item.is_invalid = True
    item.invalid_reason = "用户归档"
    await db.flush()
    return {
        "success": True,
        "message": f"已归档: {item.title[:30]}",
        "id": item.id,
        "is_invalid": item.is_invalid,
        "invalid_reason": item.invalid_reason,
    }


@crawler_router.post("/items/batch-delete")
async def batch_delete_crawler_items(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawlers")),
) -> dict[str, Any]:
    """批量归档爬虫数据。"""
    ids = payload.get("ids") or []
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="请提供要归档的 ID 列表")
    reason = str(payload.get("reason") or "用户批量归档").strip()[:500]
    stmt = (
        update(CrawlerItem)
        .where(CrawlerItem.id.in_(ids))
        .values(is_invalid=True, invalid_reason=reason)
    )
    result = await db.execute(stmt)
    await db.flush()
    return {"success": True, "archived_count": result.rowcount, "is_invalid": True}


@crawler_router.put("/items/{item_id}/mark")
async def mark_crawler_item(
    item_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawlers")),
) -> dict[str, Any]:
    """标记爬虫数据为无效/有问题。"""
    item = (await db.execute(select(CrawlerItem).where(CrawlerItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="数据不存在")
    is_invalid = bool(payload.get("is_invalid", True))
    reason = str(payload.get("reason") or "").strip()[:500]
    item.is_invalid = is_invalid
    item.invalid_reason = reason if is_invalid else None
    await db.flush()
    return {"success": True, "id": item.id, "is_invalid": item.is_invalid, "invalid_reason": item.invalid_reason}


@crawler_router.post("/items/batch-mark")
async def batch_mark_crawler_items(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawlers")),
) -> dict[str, Any]:
    """批量标记爬虫数据。"""
    ids = payload.get("ids") or []
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="请提供 ID 列表")
    is_invalid = bool(payload.get("is_invalid", True))
    reason = str(payload.get("reason") or "").strip()[:500]
    stmt = (
        update(CrawlerItem)
        .where(CrawlerItem.id.in_(ids))
        .values(is_invalid=is_invalid, invalid_reason=reason if is_invalid else None)
    )
    result = await db.execute(stmt)
    await db.flush()
    return {"success": True, "updated_count": result.rowcount, "is_invalid": is_invalid}
