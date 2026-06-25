"""竞对监控爬虫：采集竞争对手官网新闻动态。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import COMPETITORS, CRAWLER_MAX_ITEMS_PER_SOURCE, CRAWLER_MAX_ITEMS_PER_RUN
from .intelligence_agent import build_intelligence_profile, competitor_event_type

logger = logging.getLogger(__name__)


class CompetitorCrawler(BaseCrawler):
    """竞对监控爬虫：采集超图、中地、航天宏图等竞对官网新闻。"""

    name = "competitor"
    category = "competitor"

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__()
        self.sources = sources or COMPETITORS

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有竞对源。"""

        results: list[CrawlResult] = []

        for competitor in self.sources:
            try:
                items = await self._crawl_competitor(competitor)
                results.extend(items)
                self.source_reports.append({
                    "source_id": competitor.get("source_id"),
                    "name": competitor.get("name"),
                    "url": competitor.get("url"),
                    "type": competitor.get("type") or (competitor.get("selectors") or {}).get("type") or "official_site",
                    "crawl_policy": competitor.get("crawl_policy"),
                    "status": "ok",
                    "found": len(items),
                    "compliance": "robots+rate_limit",
                })
                logger.info("[competitor] %s: 获取 %d 条", competitor["name"], len(items))
            except Exception as e:
                self.source_reports.append({
                    "source_id": competitor.get("source_id"),
                    "name": competitor.get("name"),
                    "url": competitor.get("url"),
                    "type": competitor.get("type") or (competitor.get("selectors") or {}).get("type") or "official_site",
                    "crawl_policy": competitor.get("crawl_policy"),
                    "status": "error",
                    "found": 0,
                    "error": str(e),
                    "compliance": "robots+rate_limit",
                })
                logger.warning("[competitor] %s 爬取失败: %s", competitor["name"], e)

        return results[:CRAWLER_MAX_ITEMS_PER_RUN]

    async def _crawl_competitor(self, competitor: dict) -> list[CrawlResult]:
        """爬取单个竞对的新闻列表。"""

        if competitor.get("type") == "direct_pages":
            return await self._crawl_direct_pages(competitor)

        url = competitor["url"]
        base_url = competitor.get("base_url", "")
        selectors = competitor.get("selectors") or {}
        company_name = competitor["name"]

        html = await self._safe_get_text(url, source_name=company_name, source_policy=competitor.get("crawl_policy"))
        soup = BeautifulSoup(html, "lxml")

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

                content = item.get_text(" ", strip=True)
                detail_content, detail_date, detail_error = await self._fetch_detail_text(link, competitor)
                if detail_content and len(detail_content) > len(content):
                    content = detail_content
                if not _looks_like_competitor_signal(title, content, company_name):
                    continue
                pub_date = detail_date or pub_date

                # 判断事件类型
                event_type = competitor_event_type(title)
                extra = {
                    "company": company_name,
                    "event_type": event_type,
                    "monitoring_focus": self._monitoring_focus(event_type),
                    "matched_keywords": _matched_competitor_terms(title, content, company_name),
                    "detail_fetched": bool(detail_content),
                    "detail_fetch_error": detail_error,
                }
                extra["agent_profile"] = build_intelligence_profile(
                    kind="competitor",
                    title=title,
                    content=content,
                    source=company_name,
                    source_url=link,
                    matched_keywords=extra["matched_keywords"] or [event_type],
                    extra=extra,
                )

                results.append(CrawlResult(
                    category="competitor",
                    title=title,
                    source=company_name,
                    source_url=link,
                    published_at=pub_date,
                    content=content[:2000],
                    summary=title[:180],
                    extra_data=extra,
                ))

            except Exception as e:
                logger.debug("[competitor] 解析 %s 单条失败: %s", company_name, e)
                continue

        return results

    async def _fetch_detail_text(self, link: str, competitor: dict) -> tuple[str, date | None, str | None]:
        source_url = competitor.get("url") or ""
        if not link or link == source_url or not link.lower().startswith(("http://", "https://")):
            return "", None, None
        try:
            html = await self._safe_get_text(
                link,
                retries=1,
                source_name=f"{competitor.get('name')} 详情页",
                source_policy=competitor.get("crawl_policy"),
            )
            soup = BeautifulSoup(html, "lxml")
            content = self._text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, article, body")
            content = re.sub(r"\s+", " ", content or "").strip()
            pub_date = self._parse_date(f"{content} {link}")
            return content[:4000], pub_date, None
        except Exception as exc:  # noqa: BLE001
            return "", None, str(exc)[:300]

    async def _crawl_direct_pages(self, competitor: dict) -> list[CrawlResult]:
        results: list[CrawlResult] = []
        for page in (competitor.get("pages") or [])[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            try:
                parsed = await self._crawl_direct_page(competitor, page)
                if parsed is not None:
                    results.append(parsed)
            except Exception as e:
                logger.warning("[competitor] %s 直采失败: %s", page.get("name") or page.get("url"), e)
        return results

    async def _crawl_direct_page(self, competitor: dict, page: dict) -> CrawlResult | None:
        url = page["url"]
        company_name = competitor["name"]
        html = await self._safe_get_text(
            url,
            source_name=page.get("name") or company_name,
            source_policy=competitor.get("crawl_policy"),
        )
        soup = BeautifulSoup(html, "lxml")
        title = (
            page.get("title")
            or self._meta_content(soup, "ArticleTitle")
            or self._text_of_first(soup, "h1, .title, .article-title, .page-title")
            or (soup.title.get_text(" ", strip=True) if soup.title else "")
        )
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 4:
            return None

        content = self._text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, body")
        content = re.sub(r"\s+", " ", content or title).strip()
        if not _looks_like_competitor_signal(title, content, company_name):
            return None

        event_type = competitor_event_type(f"{title} {content}")
        matched_keywords = _matched_competitor_terms(title, content, company_name)
        extra = {
            "company": company_name,
            "event_type": event_type,
            "monitoring_focus": self._monitoring_focus(event_type),
            "matched_keywords": matched_keywords,
            "source_type": "competitor_direct_page",
        }
        extra["agent_profile"] = build_intelligence_profile(
            kind="competitor",
            title=title,
            content=content,
            source=page.get("name") or company_name,
            source_url=url,
            matched_keywords=matched_keywords or [event_type],
            extra=extra,
        )

        return CrawlResult(
            category="competitor",
            title=title[:500],
            source=page.get("name") or company_name,
            source_url=url[:500],
            published_at=self._parse_date(f"{content} {url}"),
            content=content[:2000],
            summary=content[:180] if content else title[:180],
            extra_data=extra,
        )

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
    def _monitoring_focus(event_type: str) -> str:
        mapping = {
            "bidding_win": "关注竞对中标客户、区域和项目能力方向。",
            "customer_case": "关注竞对新案例是否影响同区域客户信任。",
            "product_update": "关注竞对产品能力、方案包装和销售话术变化。",
            "partnership": "关注竞对生态伙伴、联合投标和区域资源。",
            "regional_push": "关注竞对区域投入和新增覆盖城市。",
            "recruitment": "关注竞对岗位扩张对应的行业或区域投入。",
            "qualification": "关注竞对资质、标准、软著对标书门槛的影响。",
        }
        return mapping.get(event_type, "归档观察竞对普通动态。")

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


def _matched_competitor_terms(title: str, content: str, company_name: str) -> list[str]:
    from .config import COMPETITOR_EVENT_KEYWORDS, COMPETITOR_KEYWORDS

    text = f"{title} {content}".lower()
    terms: list[str] = []
    for keyword in [company_name, *COMPETITOR_KEYWORDS]:
        value = str(keyword).strip()
        if value and value.lower() in text:
            terms.append(value)
    for keywords in COMPETITOR_EVENT_KEYWORDS.values():
        for keyword in keywords:
            if keyword.lower() in text and keyword not in terms:
                terms.append(keyword)
    return terms[:12]


def _looks_like_competitor_signal(title: str, content: str, company_name: str) -> bool:
    text = f"{title} {content}".lower()
    title_value = title.strip()
    navigation_words = {
        "首页",
        "关于我们",
        "联系我们",
        "加入我们",
        "隐私政策",
        "网站地图",
        "产品",
        "产品中心",
        "平台产品",
        "基础产品",
        "行业产品",
        "解决方案",
        "典型案例",
        "案例中心",
        "新闻资讯",
        "GIS学堂",
        "服务支持",
        "资料下载",
        "生态伙伴",
    }
    if title_value in navigation_words:
        return False
    if len(title_value) <= 6 and any(word in title_value for word in ("产品", "方案", "案例", "学堂")):
        return False
    return bool(_matched_competitor_terms(title, content, company_name))
