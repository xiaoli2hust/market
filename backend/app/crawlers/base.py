"""爬虫基类与数据模型。

所有具体爬虫继承 BaseCrawler，实现 crawl() 方法。
run() 方法统一处理：爬取 → 去重 → 评分 → 入库。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrawlerItem
from .config import CRAWLER_TIMEOUT, CRAWLER_USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """单次爬取结果。"""

    category: str  # bidding / news / competitor / ai
    title: str
    source: str
    source_url: str
    content: str | None = None
    summary: str | None = None
    published_at: date | None = None
    relevance_score: float | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlStats:
    """一次运行的统计。"""

    crawler_name: str
    total_found: int = 0
    new_saved: int = 0
    duplicates_skipped: int = 0
    low_score_discarded: int = 0
    errors: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "crawler_name": self.crawler_name,
            "total_found": self.total_found,
            "new_saved": self.new_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "low_score_discarded": self.low_score_discarded,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class BaseCrawler:
    """爬虫基类。子类需实现 crawl() 方法。"""

    name: str = "base"
    category: str = "news"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(CRAWLER_TIMEOUT),
                headers={"User-Agent": CRAWLER_USER_AGENT},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""

        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def crawl(self) -> list[CrawlResult]:
        """执行爬取，返回原始结果列表。子类必须实现。"""

        raise NotImplementedError

    async def _check_duplicate(self, db: AsyncSession, source_url: str, title: str) -> bool:
        """检查是否重复：URL 完全匹配 或 同分类标题完全匹配。"""

        # URL 去重
        stmt = select(CrawlerItem.id).where(CrawlerItem.source_url == source_url)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return True

        # 标题去重（同分类下标题完全相同）
        stmt = select(CrawlerItem.id).where(
            CrawlerItem.category == self.category,
            CrawlerItem.title == title,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _calculate_relevance(self, item: CrawlResult, keywords: list[str]) -> float:
        """基于关键词匹配计算相关度分数（0-100）。"""

        text = f"{item.title} {item.content or ''}".lower()
        matched = [kw for kw in keywords if kw.lower() in text]
        if not matched:
            return 10.0  # 无匹配给基础分
        score = min(len(matched) * 20, 80)
        return float(score)

    async def run(self, db: AsyncSession, keywords: list[str] | None = None) -> CrawlStats:
        """执行完整爬取流程：爬取 → 去重 → 评分 → 入库。"""

        stats = CrawlStats(crawler_name=self.name)
        stats.started_at = datetime.now(timezone.utc)

        try:
            items = await self.crawl()
            stats.total_found = len(items)
            logger.info("[%s] 爬取到 %d 条原始数据", self.name, len(items))
        except Exception as e:
            logger.error("[%s] 爬取失败: %s", self.name, e)
            stats.errors += 1
            stats.finished_at = datetime.now(timezone.utc)
            await self.close()
            return stats

        for item in items:
            try:
                # 去重
                if await self._check_duplicate(db, item.source_url, item.title):
                    stats.duplicates_skipped += 1
                    continue

                # 相关度评分
                if keywords and item.relevance_score is None:
                    item.relevance_score = self._calculate_relevance(item, keywords)

                # 生成摘要（如果还没有）
                if not item.summary and item.content:
                    item.summary = item.content[:100].strip() + ("..." if len(item.content) > 100 else "")

                # 入库
                db_item = CrawlerItem(
                    category=item.category or self.category,
                    title=item.title[:500],
                    content=item.content,
                    summary=item.summary,
                    source=item.source[:200] if item.source else None,
                    source_url=item.source_url[:500] if item.source_url else None,
                    published_at=item.published_at,
                    relevance_score=item.relevance_score,
                    extra_data=item.extra_data or None,
                )
                db.add(db_item)
                stats.new_saved += 1

            except Exception as e:
                logger.warning("[%s] 处理单条数据失败: %s", self.name, e)
                stats.errors += 1

        try:
            await db.commit()
        except Exception as e:
            logger.error("[%s] 数据库提交失败: %s", self.name, e)
            await db.rollback()
            stats.errors += 1

        stats.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[%s] 完成: 发现 %d, 新增 %d, 重复 %d, 错误 %d",
            self.name, stats.total_found, stats.new_saved,
            stats.duplicates_skipped, stats.errors,
        )
        await self.close()
        return stats
