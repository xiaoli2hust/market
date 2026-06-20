"""爬虫配置管理路由。

提供目标站点 CRUD、关键词管理、调度配置等接口。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import CrawlerSource, KeywordConfig, ScheduleConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crawler-config", tags=["crawler-config"])


# ---------------------------------------------------------------------------
# 目标站点
# ---------------------------------------------------------------------------


@router.get("/sources")
async def list_sources(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取所有目标站点，可按分类筛选。"""
    stmt = select(CrawlerSource).order_by(CrawlerSource.category, CrawlerSource.id)
    if category:
        stmt = stmt.where(CrawlerSource.category == category)
    rows = (await db.execute(stmt)).scalars().all()
    return [_source_to_dict(s) for s in rows]


@router.post("/sources")
async def create_source(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """添加目标站点。"""
    required = ["category", "name", "url"]
    for field in required:
        if not payload.get(field):
            raise HTTPException(400, f"{field} is required")

    source = CrawlerSource(
        category=payload["category"],
        name=payload["name"],
        url=payload["url"],
        base_url=payload.get("base_url"),
        selectors=payload.get("selectors"),
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
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """编辑目标站点。"""
    source = (await db.execute(
        select(CrawlerSource).where(CrawlerSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(404, "source not found")

    for field in ("category", "name", "url", "base_url", "selectors", "is_active"):
        if field in payload:
            setattr(source, field, payload[field])
    await db.flush()
    await db.refresh(source)
    return _source_to_dict(source)


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除目标站点。"""
    await db.execute(delete(CrawlerSource).where(CrawlerSource.id == source_id))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 关键词
# ---------------------------------------------------------------------------


@router.get("/keywords")
async def get_keywords(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取所有分类的关键词。"""
    rows = (await db.execute(
        select(KeywordConfig).order_by(KeywordConfig.category)
    )).scalars().all()
    if not rows:
        # 返回默认值
        return _default_keywords()
    return [{"category": r.category, "keywords": r.keywords} for r in rows]


@router.put("/keywords")
async def update_keywords(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """更新某分类的关键词。payload: {category, keywords}"""
    category = payload.get("category", "").strip()
    keywords = payload.get("keywords", [])
    if not category:
        raise HTTPException(400, "category is required")

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
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取调度配置。"""
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    if not row:
        return {
            "crawl_frequency_per_day": 2,
            "relevance_threshold": 30,
            "auto_crawl_enabled": False,
        }
    return {
        "crawl_frequency_per_day": row.crawl_frequency_per_day,
        "relevance_threshold": row.relevance_threshold,
        "auto_crawl_enabled": row.auto_crawl_enabled,
    }


@router.put("/schedule")
async def update_schedule(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """更新调度配置。"""
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
    return {
        "id": s.id,
        "category": s.category,
        "name": s.name,
        "url": s.url,
        "base_url": s.base_url,
        "selectors": s.selectors,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _default_keywords() -> list[dict[str, Any]]:
    from ..crawlers.config import BIDDING_KEYWORDS, MARKET_KEYWORDS, AI_KEYWORDS
    return [
        {"category": "bidding", "keywords": BIDDING_KEYWORDS.get("core", [])},
        {"category": "news", "keywords": MARKET_KEYWORDS},
        {"category": "ai", "keywords": AI_KEYWORDS},
        {"category": "competitor", "keywords": []},
    ]
