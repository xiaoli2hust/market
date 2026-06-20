"""剑鱼标讯 API 爬虫。

直接调用 customer.jianyu360.com 的 data-preview API，
无需 Playwright，速度快、数据完整。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrawlerItem, DingtalkConfig
from .base import BaseCrawler, CrawlResult, CrawlStats

logger = logging.getLogger(__name__)

# API 配置
_JIANYU_API_BASE = "https://customer.jianyu360.com"
_JIANYU_DATA_API = "/private/keydatademo/{key}"
_JIANYU_OPTION_API = "/private/keydataoption/{key}"


class JianyuBiddingCrawler(BaseCrawler):
    """剑鱼标讯 API 爬虫。"""

    name = "bidding"
    category = "bidding"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: str = ""
        self._customer_name: str = ""

    async def _load_config(self, db: AsyncSession) -> None:
        """从数据库加载 API key。"""
        row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
        if row and row.jianyu_password:
            self._api_key = row.jianyu_password
        # jianyu_username 存 customer name 作为备注

    async def crawl(self, db: AsyncSession | None = None) -> list[CrawlResult]:
        """调用 API 获取标讯数据。"""
        if db:
            await self._load_config(db)

        if not self._api_key:
            logger.warning("[bidding] API key 未配置，跳过")
            return []

        results: list[CrawlResult] = []

        try:
            # 调用 API（同步，API 很快）
            items, customer_name = await self._fetch_data(self._api_key)
            self._customer_name = customer_name

            for item in items:
                result = self._to_crawl_result(item)
                if result:
                    results.append(result)

            logger.info("[bidding] API 返回 %d 条标讯 (客户: %s)", len(results), customer_name)

        except Exception as e:
            logger.error("[bidding] API 调用失败: %s", e, exc_info=True)

        return results

    async def _fetch_data(self, api_key: str) -> tuple[list[dict[str, Any]], str]:
        """调用剑鱼 data-preview API。"""
        url = f"{_JIANYU_API_BASE}{_JIANYU_DATA_API.format(key=api_key)}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, params={"type": "private"})

            if resp.status_code != 200:
                raise RuntimeError(f"API 返回 HTTP {resp.status_code}")

            data = resp.json()

            if "err" in data and data["err"] != "":
                raise RuntimeError(f"API 错误: {data['err']}")

            items = data.get("data", [])
            customer_name = data.get("customername", "")

            return items, customer_name

    def _to_crawl_result(self, item: dict[str, Any]) -> CrawlResult | None:
        """将 API 数据转换为 CrawlResult。"""
        title = item.get("title", "").strip()
        if not title:
            # 尝试从 com_package 获取
            packages = item.get("com_package", [])
            if packages:
                title = packages[0].get("name", "").strip()
        if not title:
            return None

        # 提取采购人
        buyer = item.get("buyer", "")
        buyer_person = item.get("buyerperson", "")
        buyer_tel = item.get("buyertel", "")

        # 提取中标单位
        winner = item.get("winner", "")

        # 提取金额
        bid_amount = item.get("bidamount", "")

        # 提取发布时间
        pub_time = ""
        come_in_time = item.get("comeintime", 0)
        if come_in_time:
            try:
                pub_time = datetime.fromtimestamp(come_in_time).strftime("%Y-%m-%d")
            except:
                pass
        if not pub_time:
            pub_time = item.get("publishtime", "")

        # 提取关键词
        match_key = item.get("s_matchkey", "")
        show_key = item.get("showKeyString", match_key)

        # 省份/城市
        area = item.get("area", "")
        city = item.get("city", "")
        location = f"{area}-{city}" if area and city else (area or city)

        # 公告类型
        subtype = item.get("subtype", "")
        channel = item.get("channel", "")
        basic_class = item.get("basicClass", "")

        # 详情
        detail = item.get("detail", "")

        # 链接
        href = item.get("href", "")
        if not href:
            jy_href = item.get("s_jyhref", "")
            if jy_href:
                href = jy_href

        # 项目编号/名称
        project_code = item.get("projectcode", "")
        project_name = item.get("projectname", "")

        # 评分：基于业务关键词匹配
        score = self._score_item(title, detail, match_key)

        # 构造摘要
        summary_parts = []
        if buyer:
            summary_parts.append(f"采购人: {buyer}")
        if winner:
            summary_parts.append(f"中标: {winner}")
        if bid_amount:
            summary_parts.append(f"金额: {bid_amount}万元")
        if channel:
            summary_parts.append(f"渠道: {channel}")

        summary = " | ".join(summary_parts) if summary_parts else title[:100]

        # 额外数据
        extra = {
            "source": "剑鱼标讯API",
            "customer": self._customer_name,
            "buyer": buyer,
            "buyer_person": buyer_person,
            "buyer_tel": buyer_tel,
            "winner": winner,
            "bid_amount": bid_amount,
            "location": location,
            "subtype": subtype,
            "channel": channel,
            "basic_class": basic_class,
            "project_code": project_code,
            "project_name": project_name,
            "keywords": show_key,
            "autoid": item.get("autoid", ""),
        }

        # 解析发布日期
        pub_date = None
        if pub_time:
            try:
                pub_date = date.fromisoformat(pub_time[:10])
            except:
                pass

        return CrawlResult(
            category="bidding",
            title=title[:500],
            source=f"剑鱼标讯 ({self._customer_name})",
            source_url=href[:500] if href else "",
            content=detail[:2000] if detail else title,
            summary=summary[:200],
            published_at=pub_date,
            relevance_score=score,
            extra_data=extra,
        )

    def _score_item(self, title: str, detail: str, keywords: str) -> float:
        """基于业务关键词评分。"""
        from .config import JIANYU_BUSINESS_KEYWORDS

        text = f"{title} {detail} {keywords}".lower()
        max_score = 0.0

        for direction, kws in JIANYU_BUSINESS_KEYWORDS.items():
            hits = sum(1 for kw in kws if kw.lower() in text)
            if hits >= 5:
                score = 90.0
            elif hits >= 3:
                score = 70.0
            elif hits >= 2:
                score = 50.0
            elif hits >= 1:
                score = 30.0
            else:
                score = 10.0
            max_score = max(max_score, score)

        return max_score

    async def run(self, db: AsyncSession, keywords: list[str] | None = None) -> CrawlStats:
        """重写 run 方法。"""
        stats = CrawlStats(crawler_name=self.name)
        stats.started_at = datetime.now(timezone.utc)

        try:
            items = await self.crawl(db=db)
            stats.total_found = len(items)
            logger.info("[bidding] API 获取 %d 条标讯", len(items))
        except Exception as e:
            logger.error("[bidding] 爬取失败: %s", e)
            stats.errors += 1
            stats.finished_at = datetime.now(timezone.utc)
            return stats

        for item in items:
            try:
                # 去重
                source_url = item.source_url or item.title
                if await self._check_duplicate(db, source_url, item.title):
                    stats.duplicates_skipped += 1
                    continue

                # 低分过滤
                if item.relevance_score is not None and item.relevance_score < 10:
                    stats.low_score_discarded += 1
                    continue

                # 入库
                db_item = CrawlerItem(
                    category=item.category,
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
                logger.warning("[bidding] 处理单条失败: %s", e)
                stats.errors += 1

        try:
            await db.commit()
        except Exception as e:
            logger.error("[bidding] 数据库提交失败: %s", e)
            await db.rollback()
            stats.errors += 1

        stats.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[bidding] 完成: 发现 %d, 新增 %d, 重复 %d, 低分 %d, 错误 %d",
            stats.total_found, stats.new_saved,
            stats.duplicates_skipped, stats.low_score_discarded, stats.errors,
        )
        return stats
