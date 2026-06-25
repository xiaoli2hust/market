"""官方公开站点采集器：政策研判。

用于低频采集公开列表页，不做登录绕过、不处理验证码、不使用代理池。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import (
    CRAWLER_MAX_ITEMS_PER_SOURCE,
    CRAWLER_MAX_ITEMS_PER_RUN,
    POLICY_SOURCES,
)
from .intelligence_agent import build_intelligence_profile

logger = logging.getLogger(__name__)


class OfficialListCrawler(BaseCrawler):
    """官方列表页通用采集器。"""

    name = "official"
    category = "news"
    kind = "news"

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__()
        self.sources = sources or []
        self._source_query_keywords: dict[str, list[str | None]] = {}
        self.year_filter: int | None = None

    async def crawl(self) -> list[CrawlResult]:
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
                    "query_keywords": self._source_query_keywords.get(source.get("url", ""), []),
                })
                logger.info("[%s] %s: 获取 %d 条", self.name, source.get("name"), len(items))
            except Exception as e:  # noqa: BLE001
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
                    "query_keywords": self._source_query_keywords.get(source.get("url", ""), []),
                })
                logger.warning("[%s] %s 爬取失败: %s", self.name, source.get("name"), e)

        return _dedupe_by_url(results)[:CRAWLER_MAX_ITEMS_PER_RUN]

    async def _crawl_source(self, source: dict) -> list[CrawlResult]:
        if source.get("type") == "direct_pages":
            return await self._crawl_direct_pages(source)
        if source.get("type") == "api_post":
            return await self._crawl_api_source(source)

        url = source["url"]
        base_url = source.get("base_url") or url
        selectors = source.get("selectors") or {}
        html = await self._safe_get_text(url, source_name=source.get("name"), source_policy=source.get("crawl_policy"))
        soup = BeautifulSoup(html, "lxml")

        results: list[CrawlResult] = []
        candidates = self._select_candidates(soup, selectors)

        for node in candidates[: CRAWLER_MAX_ITEMS_PER_SOURCE * 2]:
            try:
                parsed = self._parse_node(node, source, base_url, selectors)
                if parsed is None:
                    continue
                parsed = await self._enrich_from_detail(parsed, source)
                results.append(parsed)
            except Exception as e:  # noqa: BLE001
                logger.debug("[%s] 解析单条失败: %s", self.name, e)

        return _dedupe_by_url(results)[:CRAWLER_MAX_ITEMS_PER_SOURCE]

    async def _enrich_from_detail(self, item: CrawlResult, source: dict) -> CrawlResult:
        """Fetch detail pages for matched list items to improve evidence quality."""

        if not item.source_url or item.source_url == source.get("url"):
            return item
        if not item.source_url.lower().startswith(("http://", "https://")):
            return item

        try:
            html = await self._safe_get_text(
                item.source_url,
                retries=1,
                source_name=f"{source.get('name')} 详情页",
                source_policy=source.get("crawl_policy"),
            )
            soup = BeautifulSoup(html, "lxml")
            title = (
                self._meta_content(soup, "ArticleTitle")
                or self._text_of_first(soup, "h1, .title, .article-title, .detail-title")
                or item.title
            )
            title = re.sub(r"\s+", " ", title or item.title).strip()
            content = self._text_of_first(
                soup,
                ".TRS_Editor, .article-content, .content, .detail, .main, article, body",
            )
            content = re.sub(r"\s+", " ", content or item.content or item.title).strip()
            pub_date = self._parse_date(f"{content} {item.source_url}") or item.published_at
            if not self._is_allowed_year(pub_date, title, content, item.source_url):
                return item
            matched_keywords = self._match_keywords_for_profile(title, content)
            if not matched_keywords:
                return item

            extra = dict(item.extra_data or {})
            extra.update({
                "detail_fetched": True,
                "matched_keywords": matched_keywords,
            })
            extra["agent_profile"] = build_intelligence_profile(
                kind=self.kind,
                title=title,
                content=content,
                source=item.source,
                source_url=item.source_url,
                matched_keywords=matched_keywords,
                extra=extra,
            )
            item.title = title[:500]
            item.content = content[:4000]
            item.summary = content[:220]
            item.published_at = pub_date
            item.relevance_score = self._profile_score(matched_keywords)
            item.extra_data = extra
        except Exception as exc:  # noqa: BLE001
            extra = dict(item.extra_data or {})
            extra["detail_fetch_error"] = str(exc)[:300]
            item.extra_data = extra
        return item

    async def _crawl_direct_pages(self, source: dict) -> list[CrawlResult]:
        results: list[CrawlResult] = []
        pages = source.get("pages") or []
        for page in pages[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            try:
                parsed = await self._crawl_direct_page(source, page)
                if parsed is not None:
                    results.append(parsed)
            except Exception as e:  # noqa: BLE001
                logger.warning("[%s] %s 直采失败: %s", self.name, page.get("name") or page.get("url"), e)
        return _dedupe_by_url(results)

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

        content = self._text_of_first(
            soup,
            ".TRS_Editor, .article-content, .content, .detail, .main, body",
        )
        content = re.sub(r"\s+", " ", content or title).strip()
        pub_date = self._parse_date(f"{content} {url}")
        if not self._is_allowed_year(pub_date, title, content, url):
            return None
        matched_keywords = self._match_keywords_for_profile(title, content)
        if not matched_keywords:
            return None

        extra = {
            "source_type": "official_direct_page",
            "source_config": source.get("name"),
            "review_state": "matched",
            "year_filter": self.year_filter,
            "matched_keywords": matched_keywords,
            "compliance": {
                "robots_checked": True,
                "rate_limited": True,
                "captcha_bypass": False,
                "login_bypass": False,
            },
        }
        extra["agent_profile"] = build_intelligence_profile(
            kind=self.kind,
            title=title,
            content=content,
            source=page.get("name") or source.get("name"),
            source_url=url,
            matched_keywords=matched_keywords,
            extra=extra,
        )

        return CrawlResult(
            category=self.category,
            title=title[:500],
            source=page.get("name") or source.get("name", "官方公开页面"),
            source_url=url[:500],
            content=content[:2000],
            summary=content[:180],
            published_at=pub_date,
            relevance_score=self._profile_score(matched_keywords),
            extra_data=extra,
        )

    def _select_candidates(self, soup: BeautifulSoup, selectors: dict) -> list:
        list_selector = selectors.get("list")
        if list_selector:
            items = soup.select(list_selector)
            if items:
                return items

        items = soup.select("li, tr, .list li, .news-list li, .article-list li")
        if items:
            return items
        return soup.select("a")

    def _parse_node(self, node, source: dict, base_url: str, selectors: dict) -> CrawlResult | None:
        title_el = self._first_select(node, selectors.get("title", "a"))
        if title_el is None:
            title_el = node if getattr(node, "name", "") == "a" else node.select_one("a")
        if title_el is None:
            return None

        title = title_el.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title)
        if len(title) < 6:
            return None

        link = self._extract_link(node, title_el, base_url, selectors)
        if _is_navigation_item(title, link):
            return None
        text = node.get_text(" ", strip=True)
        pub_date = self._parse_date(f"{text} {link}")
        if not self._is_allowed_year(pub_date, title, text, link):
            return None
        matched_keywords = self._match_keywords_for_profile(title, text)
        if not matched_keywords:
            return None
        extra = {
            "source_type": "official_public_page",
            "source_config": source.get("name"),
            "review_state": "matched",
            "year_filter": self.year_filter,
            "compliance": {
                "robots_checked": True,
                "rate_limited": True,
                "captcha_bypass": False,
                "login_bypass": False,
            },
            "matched_keywords": matched_keywords,
        }
        extra["agent_profile"] = build_intelligence_profile(
            kind=self.kind,
            title=title,
            content=text,
            source=source.get("name"),
            source_url=link,
            matched_keywords=matched_keywords,
            extra=extra,
        )

        return CrawlResult(
            category=self.category,
            title=title[:500],
            source=source.get("name", "官方公开站点"),
            source_url=link[:500],
            content=text[:2000] if text else title,
            summary=text[:180] if text else title[:120],
            published_at=pub_date,
            relevance_score=self._profile_score(matched_keywords),
            extra_data=extra,
        )

    async def _crawl_api_source(self, source: dict) -> list[CrawlResult]:
        payload = dict(source.get("payload") or {})
        query_keywords = self._query_keywords(source)
        self._source_query_keywords[source.get("url", "")] = query_keywords
        results: list[CrawlResult] = []

        for query_keyword in query_keywords:
            request_payload = dict(payload)
            if query_keyword:
                request_payload["FINDTXT"] = query_keyword
            data = await self._safe_post_json(
                source["url"],
                data=request_payload,
                headers=source.get("headers"),
                source_name=source.get("name"),
                source_policy=source.get("crawl_policy"),
            )
            if data.get("code") == 829 or data.get("captchaToken"):
                raise PermissionError(f"{source.get('name')}: 站点要求验证码，已停止采集")
            if data.get("code") not in (None, 200):
                raise RuntimeError(f"{source.get('name')}: 查询接口返回 {data.get('code')} {data.get('message')}")

            for record in self._records_from_path(data, source.get("records_path", "data.records")):
                parsed = self._parse_api_record(record, source, query_keyword)
                if parsed is not None:
                    results.append(parsed)
                if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                    break
            if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                break

        return _dedupe_by_url(results)[:CRAWLER_MAX_ITEMS_PER_SOURCE]

    def _parse_api_record(self, record: dict, source: dict, query_keyword: str | None) -> CrawlResult | None:
        title = str(record.get("title") or record.get("name") or "").strip()
        if len(title) < 6:
            return None

        base_url = source.get("base_url") or source["url"]
        link = urljoin(base_url, str(record.get("url") or record.get("href") or ""))
        pub_date = self._parse_date(str(record.get("publishTime") or record.get("date") or ""))
        content_parts = [
            title,
            str(record.get("provinceText") or ""),
            str(record.get("cityText") or ""),
            str(record.get("transactionSourcesPlatformText") or ""),
            str(record.get("businessTypeText") or ""),
            str(record.get("informationTypeText") or ""),
            str(record.get("bodyContent") or ""),
            query_keyword or "",
        ]
        content = " ".join(part for part in content_parts if part).strip()
        if not self._is_allowed_year(pub_date, title, content, link):
            return None
        matched_keywords = self._match_keywords_for_profile(title, content)
        if query_keyword and query_keyword not in matched_keywords:
            matched_keywords = [query_keyword, *matched_keywords]
        if not matched_keywords:
            return None

        extra = {
            "source_type": "official_query_api",
            "source_config": source.get("name"),
            "query_keyword": query_keyword,
            "review_state": "matched",
            "year_filter": self.year_filter,
            "compliance": {
                "robots_checked": True,
                "rate_limited": True,
                "captcha_bypass": False,
                "login_bypass": False,
            },
            "matched_keywords": matched_keywords,
            "raw_record": record,
        }
        extra["agent_profile"] = build_intelligence_profile(
            kind=self.kind,
            title=title,
            content=content,
            source=source.get("name"),
            source_url=link,
            matched_keywords=matched_keywords,
            extra=extra,
        )

        return CrawlResult(
            category=self.category,
            title=title[:500],
            source=source.get("name", "官方公开接口"),
            source_url=link[:500],
            content=content[:2000],
            summary=content[:180],
            published_at=pub_date,
            relevance_score=self._profile_score(matched_keywords),
            extra_data=extra,
        )

    def _extract_link(self, node, title_el, base_url: str, selectors: dict) -> str:
        link_selector = selectors.get("link", "a@href")
        href = ""
        if "@" in link_selector:
            tag_selector, attr = link_selector.split("@", 1)
            tag = node.select_one(tag_selector)
            if tag:
                href = tag.get(attr, "")
        if not href:
            a_tag = title_el if getattr(title_el, "name", "") == "a" else title_el.select_one("a")
            if not a_tag:
                a_tag = node.select_one("a")
            if a_tag:
                href = a_tag.get("href", "")
        return urljoin(base_url, href) if href else base_url

    def _match_keywords_for_profile(self, title: str, text: str) -> list[str]:
        haystack = f"{title} {text}".lower()
        return [kw for kw in self.runtime_keywords if kw.lower() in haystack][:12]

    def _query_keywords(self, source: dict) -> list[str | None]:
        keywords = [kw for kw in self.runtime_keywords if self._is_search_keyword(kw)]
        if keywords:
            return keywords[:20]
        configured = source.get("query_keywords") or []
        if configured:
            return [str(kw).strip() for kw in configured if str(kw).strip()][:20]
        return [None]

    @staticmethod
    def _is_search_keyword(keyword: str) -> bool:
        kw = keyword.strip()
        if not kw:
            return False
        generic_words = {
            "采购", "招标", "中标", "成交", "公开招标", "竞争性磋商",
            "单一来源", "政府采购", "公告", "项目",
        }
        return kw not in generic_words

    @staticmethod
    def _profile_score(matched_keywords: list[str]) -> float | None:
        if not matched_keywords:
            return None
        return float(min(60 + len(matched_keywords) * 8, 100))

    def _is_allowed_year(self, pub_date: date | None, *texts: str) -> bool:
        if not self.year_filter:
            return True
        if pub_date is not None:
            return pub_date.year == self.year_filter
        haystack = " ".join(text for text in texts if text)
        return str(self.year_filter) in haystack

    @staticmethod
    def _records_from_path(data: dict, path: str) -> list[dict]:
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return []
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
        return []

    @staticmethod
    def _first_select(node, selectors: str):
        for selector in selectors.split(","):
            selector = selector.strip()
            if not selector:
                continue
            found = node.select_one(selector)
            if found:
                return found
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

    @staticmethod
    def _parse_date(text: str) -> date | None:
        patterns = [
            r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])",
            r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    year, month, day = match.groups()
                    return datetime(int(year), int(month), int(day)).date()
                except ValueError:
                    return None
        return None


class PolicyCrawler(OfficialListCrawler):
    """政策 Agent：采集公开政策信号并形成研判。"""

    name = "policy"
    category = "policy"
    kind = "policy"

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__(sources or POLICY_SOURCES)
        self.year_filter = datetime.now().year

    def _match_keywords_for_profile(self, title: str, text: str) -> list[str]:
        from .config import POLICY_KEYWORDS

        haystack = f"{title} {text}".lower()
        keywords = self.runtime_keywords or POLICY_KEYWORDS
        matched = [kw for kw in keywords if kw.lower() in haystack]
        source_only_terms = {"数据局", "政数局", "大数据局"}
        strong_matches = [kw for kw in matched if kw not in source_only_terms]
        if not strong_matches:
            return []
        return matched[:12]


def _dedupe_by_url(items: list[CrawlResult]) -> list[CrawlResult]:
    result = []
    seen = set()
    for item in items:
        key = item.source_url or item.title
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


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
