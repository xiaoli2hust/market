"""行业知识爬虫：采集 AI Agent、空间数据和工程化知识源。

支持两种采集模式：
- RSS feed（稳定可靠，优先使用）
- HTTP + CSS 选择器（备用，适配 SPA 不友好的站点）
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlResult
from .config import AI_KEYWORDS, AI_SOURCES, CRAWLER_MAX_ITEMS_PER_SOURCE, CRAWLER_MAX_ITEMS_PER_RUN
from .intelligence_agent import build_intelligence_profile, contains_keyword, match_keywords

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 分层关键词：核心词必须命中至少一个，加分词提高相关度
# ---------------------------------------------------------------------------
CORE_KEYWORDS = [
    # 智能体/Agent（最核心）
    "智能体", "agent", "agentic", "multi-agent", "多智能体",
    # 大模型（次核心）
    "大模型", "llm", "gpt", "claude", "gemini", "deepseek",
    # AI 通用
    "人工智能", "ai agent", "生成式ai", "aigc",
    # 空间数据/GIS/地图
    "空间智能", "空间数据", "地理空间数据", "空间数据治理",
    "数字孪生", "cim", "实景三维", "geoai",
    "gis", "地理信息", "测绘地理信息", "时空大数据", "时空智能",
    "位置智能", "空间分析", "空间计算", "地图服务", "电子地图", "地图平台",
    "osgeo", "gdal", "proj", "qgis", "postgis", "geoserver", "mapserver",
    "openstreetmap", "osm", "geotools", "geotiff", "geopackage",
    "stac", "geoparquet", "pmtiles", "vector tile", "矢量切片",
    "cloud optimized geotiff", "cog",
    "地址治理", "地址标准化", "地址解析", "标准地址", "地理编码",
    "poi", "aoi", "遥感", "遥感影像", "点云", "lidar",
    "高精地图", "国土空间", "自然资源一张图", "地理实体",
    # 公安/政务
    "智慧公安", "智慧警务", "情指行", "政数局", "数字政府", "一网通办",
    # 技术
    "rag", "mcp", "知识图谱", "向量数据库",
]

SPATIAL_TRUSTED_SOURCE_KEYWORDS = [
    "空间数据", "地理空间", "GIS", "地理信息", "地图", "时空", "空间分析",
    "位置智能", "OpenStreetMap", "OSM", "OSGeo", "QGIS", "GeoServer",
    "GeoTools", "PostGIS", "GDAL", "PROJ", "OGC", "STAC", "GeoParquet",
    "GeoTIFF", "GeoPackage", "矢量切片", "Vector Tile", "PMTiles",
]

def _keyword_match(title: str, summary: str = "", source: dict | None = None) -> tuple[list[str], float]:
    """分层关键词匹配。返回 (命中的关键词列表, 相关度分数 0-100)。

    规则：
    - 标题匹配核心词 ≥ 1 才保留（标题没命中核心词就直接过滤）
    - 标题核心词每个 +30 分
    - 标题加分词每个 +10 分
    - 摘要匹配只做微量加分（每条 +3 分），不影响是否保留
    - 上限 100
    """
    # 标题核心词匹配（必须至少命中一个）
    title_core_hits = _dedupe_keywords(match_keywords(title, CORE_KEYWORDS))
    if not title_core_hits:
        trusted_hits = _trusted_spatial_source_hits(title, summary, source)
        if trusted_hits:
            return trusted_hits[:5], min(45 + len(trusted_hits) * 5, 75)
        return [], 0

    # 标题加分词
    core_keys = {kw.lower() for kw in CORE_KEYWORDS}
    title_bonus = _dedupe_keywords([
        kw for kw in AI_KEYWORDS if kw.lower() not in core_keys and contains_keyword(title, kw)
    ])

    # 摘要加分（只加分，不影响是否保留）
    title_hit_keys = {kw.lower() for kw in [*title_core_hits, *title_bonus]}
    summary_bonus = _dedupe_keywords([
        kw for kw in match_keywords(summary, AI_KEYWORDS) if kw.lower() not in title_hit_keys
    ]) if summary else []

    score = min(
        len(title_core_hits) * 30
        + len(title_bonus) * 10
        + len(summary_bonus) * 3,
        100,
    )
    return _dedupe_keywords(title_core_hits + title_bonus), score


def _trusted_spatial_source_hits(title: str, summary: str, source: dict | None) -> list[str]:
    selectors = (source or {}).get("selectors") or {}
    if selectors.get("knowledge_domain") != "spatial":
        return []
    source_text = " ".join([
        str((source or {}).get("name") or ""),
        str(selectors.get("scope") or ""),
        str(title or ""),
        str(summary or ""),
    ])
    return _dedupe_keywords([
        keyword for keyword in SPATIAL_TRUSTED_SOURCE_KEYWORDS
        if contains_keyword(source_text, keyword)
    ])


def _dedupe_keywords(keywords: list[str]) -> list[str]:
    result = []
    seen = set()
    for keyword in keywords:
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(keyword)
    return result


class AICrawler(BaseCrawler):
    """行业知识爬虫。"""

    name = "ai"
    category = "ai"

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__()
        self.sources = sources or AI_SOURCES

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有行业知识源。"""

        results: list[CrawlResult] = []

        for source in self.sources:
            try:
                source_type = source.get("type", "http")
                if source_type == "rss":
                    items = await self._crawl_rss(source)
                else:
                    items = await self._crawl_http(source)

                results.extend(items)
                self.source_reports.append({
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "type": source_type,
                    "crawl_policy": source.get("crawl_policy"),
                    "status": "ok",
                    "found": len(items),
                    "compliance": "robots+rate_limit",
                })
                logger.info("[ai] %s: 获取 %d 条", source["name"], len(items))
            except Exception as e:
                self.source_reports.append({
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "type": source.get("type", "http"),
                    "crawl_policy": source.get("crawl_policy"),
                    "status": "error",
                    "found": 0,
                    "error": str(e),
                    "compliance": "robots+rate_limit",
                })
                logger.warning("[ai] %s 爬取失败: %s", source["name"], e)

        return results[:CRAWLER_MAX_ITEMS_PER_RUN]

    async def _crawl_rss(self, source: dict) -> list[CrawlResult]:
        """通过 RSS feed 采集。"""

        url = source["url"]
        name = source["name"]

        text = await self._safe_get_text(url, source_name=name, source_policy=source.get("crawl_policy"))
        feed = feedparser.parse(text)

        results: list[CrawlResult] = []
        for entry in feed.entries[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title", "").strip()
            if not title or len(title) < 4:
                continue

            # 关键词过滤（标题必须命中核心词）
            summary_text = entry.get("summary", "")
            matched_kw, score = _keyword_match(title, summary_text, source)
            if not matched_kw:
                continue

            # 链接
            link = entry.get("link", url)

            # 日期
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_date = date(
                        entry.published_parsed.tm_year,
                        entry.published_parsed.tm_mon,
                        entry.published_parsed.tm_mday,
                    )
                except (ValueError, AttributeError):
                    pass

            # 摘要清理
            raw_summary = entry.get("summary", "")
            if raw_summary:
                soup = BeautifulSoup(raw_summary, "lxml")
                summary = soup.get_text(strip=True)[:300]
            else:
                summary = None

            # 子分类
            sub_category = self._classify_ai_topic(title + " " + (summary or ""))
            extra_data = {
                "matched_keywords": matched_kw[:5],
                "sub_category": sub_category,
                "source_type": "rss",
                "agent_profile": build_intelligence_profile(
                    kind="ai",
                    title=title,
                    content=summary,
                    source=name,
                    source_url=link,
                    matched_keywords=matched_kw[:5],
                    extra={"source_type": "rss", "sub_category": sub_category},
                ),
            }

            results.append(CrawlResult(
                category="ai",
                title=title,
                content=summary,
                summary=(summary[:150] + "...") if summary and len(summary) > 150 else summary,
                source=name,
                source_url=link,
                published_at=pub_date,
                relevance_score=score,
                extra_data=extra_data,
            ))

        return results

    async def _crawl_http(self, source: dict) -> list[CrawlResult]:
        """通过 HTTP + CSS 选择器采集。"""

        url = source["url"]
        base_url = source.get("base_url", "")
        selectors = source.get("selectors", {})
        name = source["name"]

        html = await self._safe_get_text(url, source_name=name, source_policy=source.get("crawl_policy"))
        soup = BeautifulSoup(html, "lxml")

        results: list[CrawlResult] = []
        list_selector = selectors.get("list", "article")
        items = soup.select(list_selector)

        for item in items[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
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
                link = url
                a_tag = title_el if title_el.name == "a" else title_el.select_one("a")
                if not a_tag:
                    a_tag = item.select_one("a")
                if a_tag:
                    href = a_tag.get("href", "")
                    if href:
                        link = urljoin(base_url or url, href)

                # 提取日期
                pub_date = None
                for sel in selectors.get("date", "").split(","):
                    date_el = item.select_one(sel.strip())
                    if date_el:
                        pub_date = self._parse_date(date_el.get_text(strip=True))
                        if pub_date:
                            break

                # 提取摘要
                summary = None
                for summary_sel in ["p", ".summary", ".desc", ".excerpt"]:
                    summary_el = item.select_one(summary_sel)
                    if summary_el:
                        text = summary_el.get_text(strip=True)
                        if text and len(text) > 10:
                            summary = text[:200]
                            break

                # 关键词过滤（标题必须命中核心词）
                matched_kw, score = _keyword_match(title, summary or "", source)
                if not matched_kw:
                    continue

                sub_category = self._classify_ai_topic(title)
                extra_data = {
                    "matched_keywords": matched_kw[:5],
                    "sub_category": sub_category,
                    "source_type": "http",
                    "agent_profile": build_intelligence_profile(
                        kind="ai",
                        title=title,
                        content=summary,
                        source=name,
                        source_url=link,
                        matched_keywords=matched_kw[:5],
                        extra={"source_type": "http", "sub_category": sub_category},
                    ),
                }

                results.append(CrawlResult(
                    category="ai",
                    title=title,
                    content=summary,
                    summary=(summary[:150] + "...") if summary and len(summary) > 150 else summary,
                    source=name,
                    source_url=link,
                    published_at=pub_date,
                    relevance_score=score,
                    extra_data=extra_data,
                ))

            except Exception as e:
                logger.debug("[ai] %s 解析单条失败: %s", name, e)
                continue

        if not results:
            discovered_feeds = await self.discover_feed_urls(
                url,
                source_name=name,
                source_policy=source.get("crawl_policy"),
                limit=3,
            )
            for feed_url in discovered_feeds:
                try:
                    feed_items = await self._crawl_rss({
                        **source,
                        "url": feed_url,
                        "type": "rss",
                        "crawl_policy": {
                            **(source.get("crawl_policy") or {}),
                            "risk_level": "rss_low",
                            "discover_feeds": False,
                        },
                    })
                    results.extend(feed_items)
                    if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                        break
                except Exception as exc:  # noqa: BLE001
                    logger.debug("[ai] %s 发现订阅源解析失败: %s", name, exc)

        return results[:CRAWLER_MAX_ITEMS_PER_SOURCE]

    @staticmethod
    def _classify_ai_topic(title: str) -> str:
        """判断 AI 资讯子分类。"""

        # 公安/政务场景
        if any(contains_keyword(title, kw) for kw in ["公安", "警务", "110", "巡防", "情指行"]):
            return "public_security"
        if any(contains_keyword(title, kw) for kw in ["政数", "政务", "一网通办", "数字政府", "工信"]):
            return "gov_affairs"
        # 智能体/Agent
        if any(contains_keyword(title, kw) for kw in ["agent", "智能体", "多智能体", "agentic"]):
            return "agent"
        # 空间数据/空间智能
        if any(contains_keyword(title, kw) for kw in [
            "空间智能", "空间数据", "地理空间", "时空", "gis", "地理信息", "测绘",
            "数字孪生", "cim", "三维", "地图", "地址", "地理编码", "遥感", "点云",
            "高精地图", "位置智能", "自然资源", "国土空间",
            "osgeo", "gdal", "proj", "qgis", "postgis", "geoserver", "mapserver",
        ]):
            return "spatial_ai"
        # 大模型
        if any(contains_keyword(title, kw) for kw in ["大模型", "llm", "gpt", "claude", "gemini", "deepseek"]):
            return "llm"
        # 一体机/硬件
        if any(contains_keyword(title, kw) for kw in ["一体机", "边缘", "信创"]):
            return "hardware"
        # 论文
        if any(contains_keyword(title, kw) for kw in ["论文", "paper", "arxiv", "acl", "aaai", "survey"]):
            return "research"
        # AIGC
        if any(contains_keyword(title, kw) for kw in ["aigc", "生成式", "文生图", "文生视频"]):
            return "aigc"
        return "general"

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """尝试多种格式解析日期。"""

        patterns = [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
            r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
            r"(\d{4})/(\d{1,2})/(\d{1,2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    return date(int(groups[0]), int(groups[1]), int(groups[2]))
                except (ValueError, IndexError):
                    continue
        return None
