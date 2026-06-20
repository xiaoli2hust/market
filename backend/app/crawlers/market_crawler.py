"""市场动态爬虫：采集政府官网政策、行业新闻。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import MARKET_KEYWORDS, MARKET_SOURCES, CRAWLER_MAX_ITEMS_PER_SOURCE

logger = logging.getLogger(__name__)


class MarketCrawler(BaseCrawler):
    """市场动态爬虫：采集自然资源部、住建部等官网新闻。"""

    name = "market"
    category = "news"

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有配置的市场动态源。"""

        results: list[CrawlResult] = []
        client = await self._get_client()

        for source in MARKET_SOURCES:
            try:
                items = await self._crawl_source(source)
                results.extend(items)
                logger.info("[market] %s: 获取 %d 条", source["name"], len(items))
            except Exception as e:
                logger.warning("[market] %s 爬取失败: %s", source["name"], e)

            if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                break

        return results[:CRAWLER_MAX_ITEMS_PER_SOURCE]

    async def _crawl_source(self, source: dict) -> list[CrawlResult]:
        """爬取单个市场动态源。"""

        client = await self._get_client()
        url = source["url"]
        base_url = source.get("base_url", "")
        selectors = source["selectors"]

        resp = await client.get(url)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        results: list[CrawlResult] = []
        list_selector = selectors.get("list", "li")
        items = soup.select(list_selector)

        for item in items[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            try:
                # 提取标题和链接
                title_el = item.select_one(selectors.get("title", "a"))
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 4:
                    continue

                # 提取链接
                link = None
                link_selector = selectors.get("link", "a@href")
                if "@" in link_selector:
                    tag = item.select_one(link_selector.split("@")[0])
                    if tag:
                        link = tag.get(link_selector.split("@")[1], "")
                else:
                    link_el = item.select_one(link_selector)
                    if link_el:
                        link = link_el.get("href", "")

                if not link:
                    # 尝试从标题元素获取
                    a_tag = item.select_one("a")
                    if a_tag:
                        link = a_tag.get("href", "")

                if link:
                    link = urljoin(base_url or url, link)
                else:
                    link = url

                # 提取日期
                pub_date = None
                date_selector = selectors.get("date", "")
                if date_selector:
                    for sel in date_selector.split(","):
                        date_el = item.select_one(sel.strip())
                        if date_el:
                            date_text = date_el.get_text(strip=True)
                            pub_date = self._parse_date(date_text)
                            if pub_date:
                                break

                # 关键词过滤
                text = title.lower()
                matched_kw = [kw for kw in MARKET_KEYWORDS if kw.lower() in text]
                if not matched_kw:
                    continue  # 跳过不相关的内容

                results.append(CrawlResult(
                    category="news",
                    title=title,
                    source=source["name"],
                    source_url=link,
                    published_at=pub_date,
                    extra_data={"matched_keywords": matched_kw},
                ))

            except Exception as e:
                logger.debug("[market] 解析单条失败: %s", e)
                continue

        return results

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """尝试多种格式解析日期。"""

        patterns = [
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
            (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", "%Y.%m.%d"),
            (r"(\d{4})/(\d{1,2})/(\d{1,2})", "%Y/%m/%d"),
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "%Y-%m-%d"),
        ]
        for pattern, fmt in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    return datetime(
                        int(groups[0]), int(groups[1]), int(groups[2])
                    ).date()
                except (ValueError, IndexError):
                    continue
        return None
