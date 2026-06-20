"""AI/Agent 资讯爬虫：采集 RSS + HTTP 源。

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
from .config import AI_KEYWORDS, AI_SOURCES, CRAWLER_MAX_ITEMS_PER_SOURCE

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
    # 空间/GIS
    "空间智能", "数字孪生", "cim", "实景三维", "geoai",
    # 公安/政务
    "智慧公安", "智慧警务", "情指行", "政数局", "数字政府", "一网通办",
    # 技术
    "rag", "mcp", "知识图谱", "向量数据库",
]


def _keyword_match(title: str, summary: str = "") -> tuple[list[str], float]:
    """分层关键词匹配。返回 (命中的关键词列表, 相关度分数 0-100)。

    规则：
    - 标题匹配核心词 ≥ 1 才保留（标题没命中核心词就直接过滤）
    - 标题核心词每个 +30 分
    - 标题加分词每个 +10 分
    - 摘要匹配只做微量加分（每条 +3 分），不影响是否保留
    - 上限 100
    """
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""

    # 标题核心词匹配（必须至少命中一个）
    title_core_hits = [kw for kw in CORE_KEYWORDS if kw in title_lower]
    if not title_core_hits:
        return [], 0

    # 标题加分词
    title_bonus = [kw for kw in AI_KEYWORDS if kw not in CORE_KEYWORDS and kw.lower() in title_lower]

    # 摘要加分（只加分，不影响是否保留）
    summary_bonus = [kw for kw in AI_KEYWORDS if kw.lower() in summary_lower] if summary_lower else []

    score = min(
        len(title_core_hits) * 30
        + len(title_bonus) * 10
        + len(summary_bonus) * 3,
        100,
    )
    return title_core_hits + title_bonus, score


class AICrawler(BaseCrawler):
    """AI/Agent 资讯爬虫。"""

    name = "ai"
    category = "ai"

    async def crawl(self) -> list[CrawlResult]:
        """爬取所有 AI 资讯源。"""

        results: list[CrawlResult] = []
        client = await self._get_client()

        for source in AI_SOURCES:
            try:
                source_type = source.get("type", "http")
                if source_type == "rss":
                    items = await self._crawl_rss(source)
                else:
                    items = await self._crawl_http(source)

                results.extend(items)
                logger.info("[ai] %s: 获取 %d 条", source["name"], len(items))
            except Exception as e:
                logger.warning("[ai] %s 爬取失败: %s", source["name"], e)

            if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE * 2:
                break

        return results[:CRAWLER_MAX_ITEMS_PER_SOURCE * 2]

    async def _crawl_rss(self, source: dict) -> list[CrawlResult]:
        """通过 RSS feed 采集。"""

        client = await self._get_client()
        url = source["url"]
        name = source["name"]

        resp = await client.get(url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        results: list[CrawlResult] = []
        for entry in feed.entries[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title", "").strip()
            if not title or len(title) < 4:
                continue

            # 关键词过滤（标题必须命中核心词）
            summary_text = entry.get("summary", "")
            matched_kw, score = _keyword_match(title, summary_text)
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

            results.append(CrawlResult(
                category="ai",
                title=title,
                content=summary,
                summary=(summary[:150] + "...") if summary and len(summary) > 150 else summary,
                source=name,
                source_url=link,
                published_at=pub_date,
                relevance_score=score,
                extra_data={
                    "matched_keywords": matched_kw[:5],
                    "sub_category": sub_category,
                    "source_type": "rss",
                },
            ))

        return results

    async def _crawl_http(self, source: dict) -> list[CrawlResult]:
        """通过 HTTP + CSS 选择器采集。"""

        client = await self._get_client()
        url = source["url"]
        base_url = source.get("base_url", "")
        selectors = source.get("selectors", {})
        name = source["name"]

        resp = await client.get(url)
        resp.raise_for_status()
        # 自动检测编码
        if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "windows-1252"):
            match = re.search(r'charset=["\']?([^"\'\s;>]+)', resp.text[:2000])
            if match:
                resp.encoding = match.group(1)
        resp.encoding = resp.encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")

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

                # 关键词过滤（标题必须命中核心词）
                matched_kw, score = _keyword_match(title, summary or "")
                if not matched_kw:
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

                sub_category = self._classify_ai_topic(title)

                results.append(CrawlResult(
                    category="ai",
                    title=title,
                    content=summary,
                    summary=(summary[:150] + "...") if summary and len(summary) > 150 else summary,
                    source=name,
                    source_url=link,
                    published_at=pub_date,
                    relevance_score=score,
                    extra_data={
                        "matched_keywords": matched_kw[:5],
                        "sub_category": sub_category,
                        "source_type": "http",
                    },
                ))

            except Exception as e:
                logger.debug("[ai] %s 解析单条失败: %s", name, e)
                continue

        return results

    @staticmethod
    def _classify_ai_topic(title: str) -> str:
        """判断 AI 资讯子分类。"""

        title_lower = title.lower()
        # 公安/政务场景
        if any(kw in title_lower for kw in ["公安", "警务", "110", "巡防", "情指行"]):
            return "public_security"
        if any(kw in title_lower for kw in ["政数", "政务", "一网通办", "数字政府", "工信"]):
            return "gov_affairs"
        # 智能体/Agent
        if any(kw in title_lower for kw in ["agent", "智能体", "多智能体", "agentic"]):
            return "agent"
        # 空间智能
        if any(kw in title_lower for kw in ["空间智能", "时空", "gis", "数字孪生", "cim", "三维"]):
            return "spatial_ai"
        # 大模型
        if any(kw in title_lower for kw in ["大模型", "llm", "gpt", "claude", "gemini", "deepseek"]):
            return "llm"
        # 一体机/硬件
        if any(kw in title_lower for kw in ["一体机", "边缘", "信创"]):
            return "hardware"
        # 论文
        if any(kw in title_lower for kw in ["论文", "paper", "arxiv", "acl", "aaai", "survey"]):
            return "research"
        # AIGC
        if any(kw in title_lower for kw in ["aigc", "生成式", "文生图", "文生视频"]):
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
