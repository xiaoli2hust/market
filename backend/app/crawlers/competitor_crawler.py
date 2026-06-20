"""竞对监控爬虫：采集竞争对手官网新闻动态。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import COMPETITORS, CRAWLER_MAX_ITEMS_PER_SOURCE

logger = logging.getLogger(__name__)


class CompetitorCrawler(BaseCrawler):
    """竞对监控爬虫：采集超图、中地、航天宏图等竞对官网新闻。"""

    name = "competitor"
    category = "competitor"

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有竞对源。"""

        results: list[CrawlResult] = []
        client = await self._get_client()

        for competitor in COMPETITORS:
            try:
                items = await self._crawl_competitor(competitor)
                results.extend(items)
                logger.info("[competitor] %s: 获取 %d 条", competitor["name"], len(items))
            except Exception as e:
                logger.warning("[competitor] %s 爬取失败: %s", competitor["name"], e)

            if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                break

        return results[:CRAWLER_MAX_ITEMS_PER_SOURCE]

    async def _crawl_competitor(self, competitor: dict) -> list[CrawlResult]:
        """爬取单个竞对的新闻列表。"""

        client = await self._get_client()
        url = competitor["url"]
        base_url = competitor.get("base_url", "")
        selectors = competitor["selectors"]
        company_name = competitor["name"]

        resp = await client.get(url)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        results: list[CrawlResult] = []
        list_selector = selectors.get("list", "li")
        items = soup.select(list_selector)

        for item in items[:10]:  # 每个竞对最多取 10 条
            try:
                # 提取标题
                title_el = None
                for sel in selectors.get("title", "a").split(","):
                    title_el = item.select_one(sel.strip())
                    if title_el:
                        break
                if not title_el:
                    title_el = item.select_one("a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title or len(title) < 4:
                    continue

                # 提取链接
                link = None
                a_tag = title_el if title_el.name == "a" else title_el.select_one("a")
                if not a_tag:
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
                            pub_date = self._parse_date(date_el.get_text(strip=True))
                            if pub_date:
                                break

                # 判断事件类型
                event_type = self._classify_event(title)

                results.append(CrawlResult(
                    category="competitor",
                    title=title,
                    source=company_name,
                    source_url=link,
                    published_at=pub_date,
                    extra_data={
                        "company": company_name,
                        "event_type": event_type,
                    },
                ))

            except Exception as e:
                logger.debug("[competitor] 解析 %s 单条失败: %s", company_name, e)
                continue

        return results

    @staticmethod
    def _classify_event(title: str) -> str:
        """根据标题关键词判断事件类型。"""

        title_lower = title.lower()
        if any(kw in title_lower for kw in ["中标", "中标公示", "成交"]):
            return "bidding_win"
        if any(kw in title_lower for kw in ["发布", "推出", "新版本", "升级", "上线"]):
            return "product_update"
        if any(kw in title_lower for kw in ["合作", "签约", "战略", "协议"]):
            return "partnership"
        if any(kw in title_lower for kw in ["招聘", "校招", "社招", "人才"]):
            return "recruitment"
        if any(kw in title_lower for kw in ["获奖", "荣誉", "奖项"]):
            return "award"
        return "news"

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """尝试多种格式解析日期。"""

        patterns = [
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", True),
            (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", True),
            (r"(\d{4})/(\d{1,2})/(\d{1,2})", True),
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", True),
        ]
        for pattern, _ in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2])).date()
                except (ValueError, IndexError):
                    continue
        return None
