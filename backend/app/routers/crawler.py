"""资讯中心 + 爬虫管理路由。

提供：
- GET /intelligence/        → 资讯列表（分页 + 筛选）
- GET /intelligence/stats   → 各分类统计
- GET /intelligence/{id}    → 单条详情
- GET /intelligence/categories → 分类字典
- GET /crawlers/status      → 爬虫状态
- POST /crawlers/{name}/run → 手动触发爬虫
- POST /crawlers/run-all    → 手动触发全部
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import CrawlerItem
from ..schemas import (
    CrawlerItemOut,
    CrawlerStatusOut,
    CrawlRunResult,
    IntelligenceStats,
)
from ..crawlers.config import CATEGORIES, MARKET_KEYWORDS, AI_KEYWORDS, JIANYU_SEARCH_KEYWORDS_SELECTED
from ..crawlers.market_crawler import MarketCrawler
from ..crawlers.competitor_crawler import CompetitorCrawler
from ..crawlers.ai_crawler import AICrawler
from ..crawlers.bidding_crawler import JianyuBiddingCrawler

logger = logging.getLogger(__name__)

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
        "label": "标讯信息",
        "keywords": JIANYU_SEARCH_KEYWORDS_SELECTED,
    },
    "market": {
        "class": MarketCrawler,
        "category": "news",
        "label": "市场动态",
        "keywords": MARKET_KEYWORDS,
    },
    "competitor": {
        "class": CompetitorCrawler,
        "category": "competitor",
        "label": "竞对监控",
        "keywords": [],
    },
    "ai": {
        "class": AICrawler,
        "category": "ai",
        "label": "AI资讯",
        "keywords": AI_KEYWORDS,
    },
}

# 运行状态缓存（进程内）
_crawler_run_status: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# 资讯中心 API
# ---------------------------------------------------------------------------


@intelligence_router.get("/")
async def list_intelligence(
    category: str | None = Query(None, description="分类筛选：bidding/news/competitor/ai"),
    keyword: str | None = Query(None, description="关键词搜索"),
    source: str | None = Query(None, description="来源筛选"),
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """资讯列表，支持多维度筛选与分页。"""

    conditions = []
    if category:
        conditions.append(CrawlerItem.category == category)
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
        except ValueError:
            pass
    if end_date:
        try:
            conditions.append(CrawlerItem.published_at <= date.fromisoformat(end_date))
        except ValueError:
            pass

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
    list_stmt = list_stmt.order_by(CrawlerItem.created_at.desc()).offset(offset).limit(page_size)

    rows = (await db.execute(list_stmt)).scalars().all()
    items = [_crawler_item_to_dict(r) for r in rows]

    return {"total": total, "items": items, "page": page, "page_size": page_size}


@intelligence_router.get("/stats")
async def intelligence_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """各分类统计。"""

    # 总数
    total = (await db.execute(select(func.count(CrawlerItem.id)))).scalar_one() or 0

    # 按分类统计
    cat_stmt = (
        select(CrawlerItem.category, func.count(CrawlerItem.id))
        .group_by(CrawlerItem.category)
    )
    cat_rows = (await db.execute(cat_stmt)).all()
    by_category = {row[0]: row[1] for row in cat_rows}

    # 今日新增
    today = datetime.now(timezone.utc).date()
    today_count = (await db.execute(
        select(func.count(CrawlerItem.id)).where(
            func.date(CrawlerItem.created_at) == today
        )
    )).scalar_one() or 0

    # 各分类最新爬取时间
    latest_crawl = {}
    for cat in ["news", "competitor", "ai", "bidding"]:
        latest = (await db.execute(
            select(func.max(CrawlerItem.created_at)).where(CrawlerItem.category == cat)
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
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """分类字典。"""

    return CATEGORIES


@intelligence_router.get("/{item_id}")
async def intelligence_detail(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
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
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """各爬虫运行状态。"""

    result = []
    for name, meta in CRAWLER_REGISTRY.items():
        # 统计该爬虫已采集的数量
        count = (await db.execute(
            select(func.count(CrawlerItem.id)).where(CrawlerItem.category == meta["category"])
        )).scalar_one() or 0

        # 最新采集时间
        latest = (await db.execute(
            select(func.max(CrawlerItem.created_at)).where(CrawlerItem.category == meta["category"])
        )).scalar_one_or_none()

        # 运行状态
        run_info = _crawler_run_status.get(name, {})
        status = run_info.get("status", "idle")

        result.append({
            "name": name,
            "category": meta["category"],
            "label": meta["label"],
            "total_collected": count,
            "last_run_at": latest,
            "last_run_stats": run_info.get("stats"),
            "status": status,
        })

    return result


@crawler_router.post("/{crawler_name}/run")
async def run_crawler(
    crawler_name: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> CrawlRunResult:
    """手动触发单个爬虫。"""

    if crawler_name not in CRAWLER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"crawler '{crawler_name}' not found")

    meta = CRAWLER_REGISTRY[crawler_name]
    crawler = meta["class"]()
    keywords = meta.get("keywords")

    _crawler_run_status[crawler_name] = {"status": "running", "stats": None}

    try:
        stats = await crawler.run(db, keywords=keywords)
        _crawler_run_status[crawler_name] = {
            "status": "completed",
            "stats": stats.to_dict(),
        }
        return CrawlRunResult(
            crawler_name=crawler_name,
            total_found=stats.total_found,
            new_saved=stats.new_saved,
            duplicates_skipped=stats.duplicates_skipped,
            errors=stats.errors,
            message=f"爬取完成：发现 {stats.total_found} 条，新增 {stats.new_saved} 条",
        )
    except Exception as e:
        _crawler_run_status[crawler_name] = {"status": "error", "stats": None}
        logger.error("爬虫 %s 运行失败: %s", crawler_name, e)
        return CrawlRunResult(
            crawler_name=crawler_name,
            errors=1,
            message=f"爬取失败: {str(e)}",
        )


@crawler_router.post("/run-all")
async def run_all_crawlers(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[CrawlRunResult]:
    """手动触发全部爬虫。"""

    results = []
    for name in CRAWLER_REGISTRY:
        meta = CRAWLER_REGISTRY[name]
        crawler = meta["class"]()
        keywords = meta.get("keywords")

        _crawler_run_status[name] = {"status": "running", "stats": None}

        try:
            stats = await crawler.run(db, keywords=keywords)
            _crawler_run_status[name] = {
                "status": "completed",
                "stats": stats.to_dict(),
            }
            results.append(CrawlRunResult(
                crawler_name=name,
                total_found=stats.total_found,
                new_saved=stats.new_saved,
                duplicates_skipped=stats.duplicates_skipped,
                errors=stats.errors,
                message=f"爬取完成：发现 {stats.total_found} 条，新增 {stats.new_saved} 条",
            ))
        except Exception as e:
            _crawler_run_status[name] = {"status": "error", "stats": None}
            logger.error("爬虫 %s 运行失败: %s", name, e)
            results.append(CrawlRunResult(
                crawler_name=name,
                errors=1,
                message=f"爬取失败: {str(e)}",
            ))

    return results


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _crawler_item_to_dict(item: CrawlerItem) -> dict[str, Any]:
    """序列化 CrawlerItem ORM 对象。"""

    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "summary": item.summary,
        "source": item.source,
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": item.relevance_score,
        "extra_data": item.extra_data,
        "is_pushed": item.is_pushed,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
