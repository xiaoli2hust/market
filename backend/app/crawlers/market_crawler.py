"""市场线索爬虫：采集政府官网政策、行业新闻。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import MARKET_KEYWORDS, MARKET_SOURCES, CRAWLER_MAX_ITEMS_PER_SOURCE, CRAWLER_MAX_ITEMS_PER_RUN
from .intelligence_agent import build_intelligence_profile

logger = logging.getLogger(__name__)


class MarketCrawler(BaseCrawler):
    """市场线索爬虫：采集自然资源部、住建部等官网新闻。"""

    name = "market"
    category = "news"

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__()
        self.sources = sources or MARKET_SOURCES

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有配置的市场线索源。"""

        results: list[CrawlResult] = []

        for source in self.sources:
            try:
                items = await self._crawl_source(source)
                results.extend(items)
                self.source_reports.append({
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "type": source.get("type") or (source.get("selectors") or {}).get("type") or "official_site",
                    "crawl_policy": source.get("crawl_policy"),
                    "status": "ok",
                    "found": len(items),
                    "compliance": "robots+rate_limit",
                })
                logger.info("[market] %s: 获取 %d 条", source["name"], len(items))
            except Exception as e:
                self.source_reports.append({
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "type": source.get("type") or (source.get("selectors") or {}).get("type") or "official_site",
                    "crawl_policy": source.get("crawl_policy"),
                    "status": "error",
                    "found": 0,
                    "error": str(e),
                    "compliance": "robots+rate_limit",
                })
                logger.warning("[market] %s 爬取失败: %s", source["name"], e)

        return results[:CRAWLER_MAX_ITEMS_PER_RUN]

    async def _crawl_source(self, source: dict) -> list[CrawlResult]:
        """爬取单个市场线索源。"""

        if source.get("type") == "direct_pages":
            return await self._crawl_direct_pages(source)

        url = source["url"]
        base_url = source.get("base_url", "")
        selectors = source.get("selectors") or {}

        html = await self._safe_get_text(url, source_name=source.get("name"), source_policy=source.get("crawl_policy"))
        soup = BeautifulSoup(html, "lxml")

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

                if _is_navigation_item(title, link):
                    continue

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
                if pub_date and pub_date < date.today() - timedelta(days=365):
                    continue

                content = item.get_text(" ", strip=True)
                detail_content, detail_date, detail_error = await self._fetch_detail_text(link, source)
                if detail_content and len(detail_content) > len(content):
                    content = detail_content
                keywords = self.runtime_keywords or MARKET_KEYWORDS
                text = f"{title} {content}".lower()
                matched_kw = [kw for kw in keywords if kw.lower() in text]
                if not matched_kw:
                    continue
                pub_date = detail_date or pub_date
                score = float(min(60 + len(matched_kw) * 8, 100))
                extra_data = {
                    "matched_keywords": matched_kw,
                    "review_state": "matched",
                    "detail_fetched": bool(detail_content),
                    "detail_fetch_error": detail_error,
                    "agent_profile": build_intelligence_profile(
                        kind="news",
                        title=title,
                        content=content,
                        source=source["name"],
                        source_url=link,
                        matched_keywords=matched_kw,
                        extra={"source_type": "official_public_page"},
                    ),
                }

                results.append(CrawlResult(
                    category="news",
                    title=title,
                    content=content[:2000],
                    summary=content[:180] if content else title,
                    source=source["name"],
                    source_url=link,
                    published_at=pub_date,
                    relevance_score=score,
                    extra_data=extra_data,
                ))

            except Exception as e:
                logger.debug("[market] 解析单条失败: %s", e)
                continue

        return results

    async def _fetch_detail_text(self, link: str, source: dict) -> tuple[str, date | None, str | None]:
        source_url = source.get("url") or ""
        if not link or link == source_url or not link.lower().startswith(("http://", "https://")):
            return "", None, None
        try:
            html = await self._safe_get_text(
                link,
                retries=1,
                source_name=f"{source.get('name')} 详情页",
                source_policy=source.get("crawl_policy"),
            )
            soup = BeautifulSoup(html, "lxml")
            content = self._text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, article, body")
            content = re.sub(r"\s+", " ", content or "").strip()
            pub_date = self._parse_date(f"{content} {link}")
            return content[:4000], pub_date, None
        except Exception as exc:  # noqa: BLE001
            return "", None, str(exc)[:300]

    async def _crawl_direct_pages(self, source: dict) -> list[CrawlResult]:
        results: list[CrawlResult] = []
        for page in (source.get("pages") or [])[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            try:
                parsed = await self._crawl_direct_page(source, page)
                if parsed is not None:
                    results.append(parsed)
            except Exception as e:
                logger.warning("[market] %s 直采失败: %s", page.get("name") or page.get("url"), e)
        return results

    async def _crawl_direct_page(self, source: dict, page: dict) -> CrawlResult | None:
        url = page["url"]
        html = await self._safe_get_text(
            url,
            source_name=page.get("name") or source.get("name"),
            source_policy=source.get("crawl_policy"),
        )
        soup = BeautifulSoup(html, "lxml")
        title = (
            page.get("title")
            or self._meta_content(soup, "ArticleTitle")
            or self._text_of_first(soup, "h1, .title, .article-title, .detail-title")
            or (soup.title.get_text(" ", strip=True) if soup.title else "")
        )
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 6:
            return None

        content = self._text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, body")
        content = re.sub(r"\s+", " ", content or title).strip()
        pub_date = self._parse_date(f"{content} {url}")
        keywords = self.runtime_keywords or MARKET_KEYWORDS
        text = f"{title} {content}".lower()
        matched_kw = [kw for kw in keywords if kw.lower() in text]
        if not matched_kw:
            return None

        score = float(min(60 + len(matched_kw) * 8, 100))
        extra_data = {
            "matched_keywords": matched_kw[:12],
            "review_state": "matched",
            "agent_profile": build_intelligence_profile(
                kind="news",
                title=title,
                content=content,
                source=page.get("name") or source.get("name"),
                source_url=url,
                matched_keywords=matched_kw[:12],
                extra={"source_type": "official_direct_page"},
            ),
        }
        return CrawlResult(
            category="news",
            title=title[:500],
            content=content[:2000],
            summary=content[:180],
            source=page.get("name") or source.get("name", "官方公开页面"),
            source_url=url[:500],
            published_at=pub_date,
            relevance_score=score,
            extra_data=extra_data,
        )

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """尝试多种格式解析日期。"""

        patterns = [
            (r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", "%Y%m%d"),
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

    @staticmethod
    def _text_of_first(soup: BeautifulSoup, selectors: str) -> str:
        for selector in selectors.split(","):
            selector = selector.strip()
            if not selector:
                continue
            found = soup.select_one(selector)
            if found:
                text = found.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    @staticmethod
    def _meta_content(soup: BeautifulSoup, name: str) -> str:
        found = soup.select_one(f'meta[name="{name}"], meta[property="{name}"]')
        if not found:
            return ""
        return str(found.get("content") or "").strip()


def _is_navigation_item(title: str, link: str) -> bool:
    title_value = title.strip()
    if not title_value:
        return True
    if not link or link.strip().lower().startswith(("javascript:", "#")):
        return True
    navigation_words = {
        "首页", "关于我们", "联系我们", "加入我们", "网站地图", "更多", "更多>>",
        "新闻", "资讯", "政策", "通知公告", "专题", "专题专栏", "服务", "产品",
        "解决方案", "公众号矩阵", "Cloud&AI",
    }
    if title_value in navigation_words:
        return True
    if len(title_value) <= 8 and any(word in title_value for word in ("矩阵", "频道", "栏目", "专题")):
        return True
    return False
