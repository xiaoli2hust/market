"""爬虫配置管理路由。

提供目标站点 CRUD、关键词管理、调度配置等接口。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import CrawlerSource, KeywordConfig, ScheduleConfig
from ..crawlers.policy import build_source_strategy_profile, normalize_crawl_policy, policy_summary
from ..seed_data import complete_crawler_source_rules
from ..services.crawler_scheduler import build_crawler_schedule_state, get_scheduler_state
from ..validation import validate_http_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crawler-config", tags=["crawler-config"])

ACTIVE_CONFIG_CATEGORIES = {"bidding", "policy", "news", "competitor", "ai"}
TARGET_SOURCE_CATEGORIES = {"bidding", "policy", "news", "competitor", "ai"}
TARGET_SOURCE_CATEGORY_ORDER = {
    "bidding": 1,
    "policy": 2,
    "news": 3,
    "competitor": 4,
    "ai": 5,
}


# ---------------------------------------------------------------------------
# 目标站点
# ---------------------------------------------------------------------------


@router.get("/sources")
async def list_sources(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> list[dict[str, Any]]:
    """获取所有目标站点，可按分类筛选。"""
    category_order = case(
        *[
            (CrawlerSource.category == name, order)
            for name, order in TARGET_SOURCE_CATEGORY_ORDER.items()
        ],
        else_=99,
    )
    stmt = select(CrawlerSource).order_by(category_order, CrawlerSource.id)
    if category:
        if category not in TARGET_SOURCE_CATEGORIES:
            return []
        stmt = stmt.where(CrawlerSource.category == category)
    else:
        stmt = stmt.where(CrawlerSource.category.in_(list(TARGET_SOURCE_CATEGORIES)))
    rows = (await db.execute(stmt)).scalars().all()
    serialized = [_source_to_dict(s) for s in rows]
    return sorted(
        serialized,
        key=lambda item: (
            TARGET_SOURCE_CATEGORY_ORDER.get(item["category"], 99),
            item.get("strategy_sort_rank") or 9999,
            item["name"],
        ),
    )


@router.post("/sources")
async def create_source(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, Any]:
    """添加目标站点。"""
    required = ["category", "name", "url"]
    for field in required:
        if not payload.get(field):
            raise HTTPException(400, f"{field} is required")
    if payload["category"] not in TARGET_SOURCE_CATEGORIES:
        raise HTTPException(400, "unsupported source category")
    payload["url"] = validate_http_url(payload.get("url"), "URL")
    if "base_url" in payload:
        payload["base_url"] = validate_http_url(payload.get("base_url"), "Base URL", allow_empty=True)

    candidate = complete_crawler_source_rules({
        "category": payload["category"],
        "name": payload["name"],
        "selectors": payload.get("selectors") or {},
        "is_active": payload.get("is_active", True),
    })
    candidate["is_active"] = payload.get("is_active", True)
    if candidate["is_active"] and not _source_can_run(candidate):
        raise HTTPException(400, _source_readiness(candidate)["reason"])

    source = CrawlerSource(
        category=payload["category"],
        name=payload["name"],
        url=payload["url"],
        base_url=payload.get("base_url"),
        selectors=candidate["selectors"],
        is_active=payload.get("is_active", True),
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return _source_to_dict(source)


@router.put("/sources/{source_id}")
async def update_source(
    source_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, Any]:
    """编辑目标站点。"""
    source = (await db.execute(
        select(CrawlerSource).where(CrawlerSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(404, "source not found")
    if (source.selectors or {}).get("protected"):
        raise HTTPException(403, "protected source cannot be edited")

    next_values = {
        "category": source.category,
        "selectors": source.selectors or {},
        "is_active": source.is_active,
    }
    for field in ("category", "selectors", "is_active"):
        if field in payload:
            next_values[field] = payload[field]
    if next_values["category"] not in TARGET_SOURCE_CATEGORIES:
        raise HTTPException(400, "unsupported source category")
    completed_next = complete_crawler_source_rules({
        "category": next_values["category"],
        "name": payload.get("name") or source.name,
        "selectors": next_values["selectors"] or {},
    })
    next_values["selectors"] = completed_next["selectors"]
    if "selectors" in payload or "category" in payload:
        payload["selectors"] = next_values["selectors"]
    if "url" in payload:
        payload["url"] = validate_http_url(payload.get("url"), "URL")
    if "base_url" in payload:
        payload["base_url"] = validate_http_url(payload.get("base_url"), "Base URL", allow_empty=True)
    if next_values["is_active"] and not _source_can_run(next_values):
        raise HTTPException(400, _source_readiness(next_values)["reason"])

    for field in ("category", "name", "url", "base_url", "selectors", "is_active"):
        if field in payload:
            if field == "category" and payload[field] not in TARGET_SOURCE_CATEGORIES:
                raise HTTPException(400, "unsupported source category")
            setattr(source, field, payload[field])
    await db.flush()
    await db.refresh(source)
    return _source_to_dict(source)


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, str]:
    """删除目标站点。"""
    source = (await db.execute(
        select(CrawlerSource).where(CrawlerSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(404, "source not found")
    if (source.selectors or {}).get("protected"):
        raise HTTPException(403, "protected source cannot be deleted")
    await db.execute(delete(CrawlerSource).where(CrawlerSource.id == source_id))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 关键词
# ---------------------------------------------------------------------------


@router.get("/keywords")
async def get_keywords(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> list[dict[str, Any]]:
    """获取所有分类的关键词。"""
    rows = (await db.execute(
        select(KeywordConfig)
        .where(KeywordConfig.category.in_(list(ACTIVE_CONFIG_CATEGORIES)))
        .order_by(KeywordConfig.category)
    )).scalars().all()
    defaults = {item["category"]: item["keywords"] for item in _default_keywords()}
    for row in rows:
        defaults[row.category] = row.keywords
    return [{"category": category, "keywords": keywords} for category, keywords in defaults.items()]


@router.put("/keywords")
async def update_keywords(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, Any]:
    """更新某分类的关键词。payload: {category, keywords}"""
    category = payload.get("category", "").strip()
    keywords = payload.get("keywords", [])
    if not category:
        raise HTTPException(400, "category is required")
    if category not in ACTIVE_CONFIG_CATEGORIES:
        raise HTTPException(400, "unsupported keyword category")

    existing = (await db.execute(
        select(KeywordConfig).where(KeywordConfig.category == category)
    )).scalar_one_or_none()

    if existing:
        existing.keywords = keywords
    else:
        db.add(KeywordConfig(category=category, keywords=keywords))
    return {"category": category, "keywords": keywords}


# ---------------------------------------------------------------------------
# 调度配置
# ---------------------------------------------------------------------------


@router.get("/schedule")
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, Any]:
    """获取调度配置。"""
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    config = {
        "crawl_frequency_per_day": row.crawl_frequency_per_day if row else 2,
        "relevance_threshold": row.relevance_threshold if row else 30,
        "auto_crawl_enabled": row.auto_crawl_enabled if row else False,
    }
    schedule = await build_crawler_schedule_state(
        db,
        int(config["crawl_frequency_per_day"]),
        bool(config["auto_crawl_enabled"]),
    )
    latest_finished = schedule["last_run_at"]
    next_run_at = schedule["next_run_at"]
    return {
        **config,
        "last_run_at": latest_finished.isoformat() if latest_finished else None,
        "next_run_at": next_run_at.isoformat() if next_run_at else None,
        "crawler_next_runs": _serialize_datetimes(schedule["crawler_next_runs"]),
        "interval_hours": schedule["interval_hours"],
        "scheduler_status": "enabled" if config["auto_crawl_enabled"] else "disabled",
        "runtime": get_scheduler_state(),
    }


@router.put("/schedule")
async def update_schedule(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:crawler")),
) -> dict[str, Any]:
    """更新调度配置。"""
    if "crawl_frequency_per_day" in payload:
        value = int(payload["crawl_frequency_per_day"])
        if value < 1 or value > 24:
            raise HTTPException(400, "每天采集次数必须在 1-24 之间")
        payload["crawl_frequency_per_day"] = value
    if "relevance_threshold" in payload:
        value = float(payload["relevance_threshold"])
        if value < 0 or value > 100:
            raise HTTPException(400, "相关性阈值必须在 0-100 之间")
        payload["relevance_threshold"] = value
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    if row:
        for field in ("crawl_frequency_per_day", "relevance_threshold", "auto_crawl_enabled"):
            if field in payload:
                setattr(row, field, payload[field])
    else:
        db.add(ScheduleConfig(
            crawl_frequency_per_day=payload.get("crawl_frequency_per_day", 2),
            relevance_threshold=payload.get("relevance_threshold", 30),
            auto_crawl_enabled=payload.get("auto_crawl_enabled", False),
        ))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_to_dict(s: CrawlerSource) -> dict[str, Any]:
    selectors = s.selectors or {}
    source_type = selectors.get("type") or selectors.get("source_type")
    crawl_policy = normalize_crawl_policy(selectors, source_type=source_type, category=s.category)
    strategy_profile = build_source_strategy_profile({
        "category": s.category,
        "name": s.name,
        "url": s.url,
        "base_url": s.base_url,
        "selectors": selectors,
        "is_active": s.is_active,
    })
    readiness = _source_readiness({
        "category": s.category,
        "selectors": selectors,
        "is_active": s.is_active,
    })
    runtime = _source_runtime_state(s)
    return {
        "id": s.id,
        "category": s.category,
        "name": s.name,
        "url": s.url,
        "base_url": s.base_url,
        "selectors": s.selectors,
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
        "is_active": s.is_active,
        "capability_status": readiness["status"],
        "capability_reason": readiness["reason"],
        **runtime,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _source_runtime_state(s: CrawlerSource) -> dict[str, Any]:
    cooldown_until = _ensure_aware(s.cooldown_until)
    is_cooling = bool(cooldown_until and cooldown_until > datetime.now(timezone.utc))
    runtime_status = "cooling" if is_cooling else (s.runtime_status or "pending")
    reason = _runtime_reason(runtime_status, s)
    return {
        "runtime_status": runtime_status,
        "runtime_reason": reason,
        "consecutive_failures": int(s.consecutive_failures or 0),
        "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
        "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
        "last_error_at": s.last_error_at.isoformat() if s.last_error_at else None,
        "last_diagnosis_code": s.last_diagnosis_code,
        "last_diagnosis_label": s.last_diagnosis_label,
        "last_error_message": s.last_error_message,
        "last_cursor": s.last_cursor,
        "last_found": int(s.last_found or 0),
        "last_saved": int(s.last_saved or 0),
    }


def _runtime_reason(runtime_status: str, s: CrawlerSource) -> str:
    if runtime_status == "cooling":
        return "近期连续异常，系统已自动冷却，冷却结束后再参与采集"
    if runtime_status == "healthy":
        return "最近一次采集可正常访问并完成处理"
    if runtime_status == "empty":
        return "最近一次可正常访问，但没有命中当前关键词"
    if runtime_status == "blocked":
        return "最近一次被站点规则或访问限制拦截，已按反爬策略退避"
    if runtime_status == "error":
        return s.last_error_message or "最近一次采集异常，需要检查解析规则或站点访问"
    if runtime_status == "skipped":
        return s.last_error_message or "最近一次因配置不完整跳过"
    return "尚未运行或暂无采集记录"


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _source_readiness(source: dict[str, Any]) -> dict[str, str]:
    selectors = source.get("selectors") or {}
    source_type = selectors.get("type") or selectors.get("source_type") or "official_site"
    category = source.get("category")
    if selectors.get("protected"):
        return {"status": "ready", "reason": "当前主链路来源，已接入运行链路"}
    if category == "bidding":
        if source_type in {"api", "browser"}:
            return {
                "status": "candidate",
                "reason": "此类标讯源需要专用授权或渲染链路，当前先作为候选源管理",
            }
        if source_type == "direct_pages":
            if selectors.get("pages"):
                return {"status": "ready", "reason": "已有直采页面清单，可参与公开标讯低频采集"}
            return {"status": "needs_selectors", "reason": "直采标讯源需要页面清单映射"}
        if selectors.get("list") and selectors.get("title"):
            return {"status": "ready", "reason": "已有解析规则，可参与公开标讯低频采集"}
        return {
            "status": "needs_selectors",
            "reason": "缺少列表和标题解析规则，启用后无法稳定采集",
        }
    if source_type == "browser":
        return {
            "status": "not_connected",
            "reason": "浏览器渲染采集尚未接入当前采集引擎",
        }
    if source_type == "rss":
        if category == "ai":
            return {"status": "ready", "reason": "行业知识采集引擎已支持 RSS 来源"}
        return {"status": "not_connected", "reason": "当前分类尚未接入 RSS 解析链路"}
    if source_type == "api":
        return {"status": "not_connected", "reason": "接口采集需要专用授权链路，当前先作为候选源管理"}
    if source_type == "api_post":
        if selectors.get("payload") is not None and selectors.get("records_path"):
            return {"status": "ready", "reason": "已有查询参数和字段路径，可参与低频公开接口采集"}
        return {"status": "not_connected", "reason": "接口采集缺少请求参数或字段路径，当前先作为候选源管理"}
    if source_type == "direct_pages":
        if selectors.get("pages"):
            return {"status": "ready", "reason": "已有直采页面清单，可参与低频采集"}
        return {"status": "not_connected", "reason": "直采页需要页面清单映射，当前先作为候选源管理"}
    has_selectors = bool(selectors.get("list") and selectors.get("title"))
    if not has_selectors:
        return {
            "status": "needs_selectors",
            "reason": "缺少列表和标题解析规则，启用后无法稳定采集",
        }
    return {"status": "ready", "reason": "已有解析规则，可参与低频采集"}


def _source_can_run(source: dict[str, Any]) -> bool:
    return _source_readiness(source)["status"] == "ready"


def _serialize_datetimes(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_datetimes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_datetimes(item) for item in value]
    return value


def _default_keywords() -> list[dict[str, Any]]:
    from ..crawlers.config import (
        AI_KEYWORDS,
        COMPETITOR_KEYWORDS,
        JIANYU_SEARCH_KEYWORDS_SELECTED,
        MARKET_KEYWORDS,
        POLICY_KEYWORDS,
    )

    return [
        {"category": "bidding", "keywords": JIANYU_SEARCH_KEYWORDS_SELECTED},
        {"category": "policy", "keywords": POLICY_KEYWORDS},
        {"category": "news", "keywords": MARKET_KEYWORDS},
        {"category": "ai", "keywords": AI_KEYWORDS},
        {"category": "competitor", "keywords": COMPETITOR_KEYWORDS},
    ]
