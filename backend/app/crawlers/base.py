"""爬虫基类与数据模型。

所有具体爬虫继承 BaseCrawler，实现 crawl() 方法。
run() 方法统一处理：爬取 → 去重 → 评分 → 入库。
"""

from __future__ import annotations

import logging
import asyncio
import subprocess
import re
import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrawlerItem, EvidenceRecord, IntelligenceEvent, ScheduleConfig
from .config import (
    CRAWLER_MIN_REQUEST_INTERVAL,
    CRAWLER_RELEVANCE_THRESHOLD,
    CRAWLER_RESPECT_ROBOTS,
    CRAWLER_TIMEOUT,
    CRAWLER_USER_AGENT,
)
from .policy import normalize_crawl_policy
from .base_utils import (
    _amount_from_extra_or_text,
    _clean_text,
    _decode_response_bytes,
    _looks_like_js_challenge,
    _matched_keywords_from_extra,
    _notice_type_from_extra,
    _published_datetime,
    _retry_after_seconds,
)

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
    source_reports: list[dict[str, Any]] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    raw_by_source: dict[str, int] = field(default_factory=dict)
    saved_by_source: dict[str, int] = field(default_factory=dict)
    duplicate_by_source: dict[str, int] = field(default_factory=dict)
    discarded_by_source: dict[str, int] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    latest_by_source: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if not self.started_at or not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

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
            "duration_ms": self.duration_ms,
            "source_reports": self.source_reports,
            "error_messages": self.error_messages,
            "raw_by_source": self.raw_by_source,
            "saved_by_source": self.saved_by_source,
            "duplicate_by_source": self.duplicate_by_source,
            "discarded_by_source": self.discarded_by_source,
            "data_quality": self.data_quality,
            "latest_by_source": self.latest_by_source,
        }


class BaseCrawler:
    """爬虫基类。子类需实现 crawl() 方法。"""

    name: str = "base"
    category: str = "news"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self.source_reports: list[dict[str, Any]] = []
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._last_request_at_by_origin: dict[str, float] = {}
        self._conditional_cache: dict[str, dict[str, str]] = {}
        self._content_hash_by_url: dict[str, str] = {}
        self.runtime_keywords: list[str] = []

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

    async def _safe_get(
        self,
        url: str,
        *,
        retries: int = 2,
        source_name: str | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """合规低频访问公开页面：遵守 robots、限速、指数退避。"""

        policy = normalize_crawl_policy(source_policy)
        if CRAWLER_RESPECT_ROBOTS and policy.get("respect_robots") and not await self._can_fetch(url):
            raise PermissionError(f"robots.txt 不允许采集: {url}")

        client = await self._get_client()
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            await self._respect_interval(url, source_policy=policy)
            try:
                request_headers = self._conditional_request_headers(url, policy)
                resp = await client.get(url, headers=request_headers or None)
                if resp.status_code == 304:
                    return resp
                if resp.status_code == 429:
                    if attempt < retries:
                        await asyncio.sleep(_retry_after_seconds(resp.headers.get("Retry-After"), attempt))
                        continue
                    raise RuntimeError("HTTP 429: 站点限制访问")
                if resp.status_code == 403:
                    raise RuntimeError("HTTP 403: 站点限制访问")
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "").lower()
                if ("html" in content_type or "text" in content_type) and _looks_like_js_challenge(
                    _decode_response_bytes(resp.content)
                ):
                    label = f"{source_name}: " if source_name else ""
                    raise RuntimeError(f"{label}站点存在安全挑战，已停止采集")
                self._remember_conditional_headers(url, resp, policy)
                return resp
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= retries:
                    break
                await asyncio.sleep(1.5 * (attempt + 1))
        label = f"{source_name}: " if source_name else ""
        raise RuntimeError(f"{label}{last_error}")

    async def _safe_get_text(
        self,
        url: str,
        *,
        retries: int = 2,
        source_name: str | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> str:
        """获取文本内容并尽量修正中文站点编码。"""

        try:
            resp = await self._safe_get(url, retries=retries, source_name=source_name, source_policy=source_policy)
            if resp.status_code == 304:
                return ""
            if resp.encoding and resp.encoding.lower() in {"iso-8859-1", "windows-1252"}:
                resp.encoding = "utf-8"
            resp.encoding = resp.encoding or "utf-8"
            text = resp.text
            policy = normalize_crawl_policy(source_policy)
            if policy.get("use_conditional_request"):
                fingerprint = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
                if self._content_hash_by_url.get(url) == fingerprint:
                    return ""
                self._content_hash_by_url[url] = fingerprint
            return text
        except PermissionError:
            raise
        except Exception as exc:  # noqa: BLE001
            try:
                return await self._curl_get_text(url, source_name=source_name, source_policy=source_policy)
            except Exception as curl_exc:  # noqa: BLE001
                label = f"{source_name}: " if source_name else ""
                raise RuntimeError(f"{label}{exc}; curl fallback failed: {curl_exc}") from curl_exc

    async def _curl_get_text(
        self,
        url: str,
        *,
        source_name: str | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> str:
        """HTTP 客户端兼容兜底；仍然遵守 robots、限速和反爬停止原则。"""

        policy = normalize_crawl_policy(source_policy)
        if CRAWLER_RESPECT_ROBOTS and policy.get("respect_robots") and not await self._can_fetch(url):
            raise PermissionError(f"robots.txt 不允许采集: {url}")

        await self._respect_interval(url, source_policy=policy)
        marker = b"\n__CRAWLER_HTTP_STATUS__:"
        cmd = [
            "curl",
            "-L",
            "-sS",
            "--compressed",
            "--max-time",
            str(CRAWLER_TIMEOUT),
            "-A",
            CRAWLER_USER_AGENT,
            "-w",
            marker.decode("ascii") + "%{http_code}",
            url,
        ]
        for header, value in self._conditional_request_headers(url, policy).items():
            cmd[-1:-1] = ["-H", f"{header}: {value}"]

        def _run_curl() -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(cmd, capture_output=True, check=False)

        completed = await asyncio.to_thread(_run_curl)
        if completed.returncode != 0:
            stderr = _decode_response_bytes(completed.stderr).strip()
            raise RuntimeError(stderr or f"curl exited with {completed.returncode}")

        if marker not in completed.stdout:
            raise RuntimeError("curl response missing status marker")
        body_bytes, status_bytes = completed.stdout.rsplit(marker, 1)
        status_text = status_bytes.decode("ascii", errors="ignore").strip().splitlines()[0]
        status = int(status_text or "0")
        body = _decode_response_bytes(body_bytes)

        if status == 304:
            return ""
        if status in {403, 429}:
            raise RuntimeError(f"HTTP {status}: 站点限制访问")
        if status >= 400:
            raise RuntimeError(f"HTTP {status}: 站点返回异常状态")
        if _looks_like_js_challenge(body):
            label = f"{source_name}: " if source_name else ""
            raise RuntimeError(f"{label}站点存在安全挑战，已停止采集")

        return body

    async def _safe_post_json(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 2,
        source_name: str | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """合规低频 POST 公开查询接口，返回 JSON。"""

        policy = normalize_crawl_policy(source_policy)
        if CRAWLER_RESPECT_ROBOTS and policy.get("respect_robots") and not await self._can_fetch(url):
            raise PermissionError(f"robots.txt 不允许采集: {url}")

        client = await self._get_client()
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            await self._respect_interval(url, source_policy=policy)
            try:
                resp = await client.post(url, data=data or {}, headers=headers)
                if resp.status_code == 429:
                    if attempt < retries:
                        await asyncio.sleep(_retry_after_seconds(resp.headers.get("Retry-After"), attempt))
                        continue
                    raise RuntimeError("HTTP 429: 站点限制访问")
                if resp.status_code == 403:
                    raise RuntimeError("HTTP 403: 站点限制访问")
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= retries:
                    break
                await asyncio.sleep(1.5 * (attempt + 1))
        label = f"{source_name}: " if source_name else ""
        raise RuntimeError(f"{label}{last_error}")

    async def _respect_interval(self, url: str, *, source_policy: dict[str, Any] | None = None) -> None:
        origin = _origin_key(url)
        min_interval = _policy_interval_seconds(source_policy)
        now = asyncio.get_running_loop().time()
        elapsed = now - float(self._last_request_at_by_origin.get(origin, 0.0))
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_at_by_origin[origin] = asyncio.get_running_loop().time()

    def _conditional_request_headers(self, url: str, policy: dict[str, Any] | None = None) -> dict[str, str]:
        normalized = normalize_crawl_policy(policy)
        if not normalized.get("use_conditional_request"):
            return {}
        cached = self._conditional_cache.get(url) or {}
        headers: dict[str, str] = {}
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]
        return headers

    def _remember_conditional_headers(
        self,
        url: str,
        resp: httpx.Response,
        policy: dict[str, Any] | None = None,
    ) -> None:
        normalized = normalize_crawl_policy(policy)
        if not normalized.get("use_conditional_request"):
            return
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        if not etag and not last_modified:
            return
        self._conditional_cache[url] = {
            **({"etag": etag} if etag else {}),
            **({"last_modified": last_modified} if last_modified else {}),
        }

    async def discover_feed_urls(
        self,
        url: str,
        *,
        source_name: str | None = None,
        source_policy: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[str]:
        """Discover RSS/sitemap URLs at very low frequency for sources that opt in."""

        policy = normalize_crawl_policy(source_policy)
        if not policy.get("discover_feeds"):
            return []
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return []
        origin = f"{parsed.scheme}://{parsed.netloc}"
        candidates = [
            urljoin(origin, "/sitemap.xml"),
            urljoin(origin, "/rss.xml"),
            urljoin(origin, "/feed.xml"),
            urljoin(origin, "/feed"),
        ]
        discovered: list[str] = []
        for candidate in candidates:
            if len(discovered) >= limit:
                break
            try:
                text = await self._safe_get_text(
                    candidate,
                    retries=0,
                    source_name=f"{source_name or origin} 发现入口",
                    source_policy={**policy, "discover_feeds": False},
                )
            except Exception:
                continue
            for found_url in _extract_feed_or_sitemap_urls(text, origin):
                if found_url not in discovered:
                    discovered.append(found_url)
                if len(discovered) >= limit:
                    break
        return discovered

    async def _can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True

        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots_cache:
            robots_url = urljoin(origin, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                await self._respect_interval(robots_url, source_policy={"risk_level": "normal_public"})
                client = await self._get_client()
                resp = await client.get(robots_url, timeout=10)
                if resp.status_code >= 400:
                    self._robots_cache[origin] = None
                else:
                    parser.parse(resp.text.splitlines())
                    self._robots_cache[origin] = parser
            except Exception:
                self._robots_cache[origin] = None

        parser = self._robots_cache.get(origin)
        if parser is None:
            return True
        return parser.can_fetch(CRAWLER_USER_AGENT, url)

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

    def _match_keywords(self, item: CrawlResult, keywords: list[str]) -> list[str]:
        """返回标题/正文命中的关键词。"""

        text = f"{item.title} {item.content or ''}".lower()
        return [kw for kw in keywords if kw.lower() in text]

    def _calculate_relevance(self, item: CrawlResult, keywords: list[str]) -> float:
        """基于关键词匹配计算相关度分数（0-100）。"""

        matched = self._match_keywords(item, keywords)
        if not matched:
            return 10.0  # 无匹配给基础分
        score = min(20 + len(matched) * 20, 100)
        return float(score)

    async def run(self, db: AsyncSession, keywords: list[str] | None = None) -> CrawlStats:
        """执行完整爬取流程：爬取 → 去重 → 评分 → 入库。"""

        stats = CrawlStats(crawler_name=self.name)
        stats.started_at = datetime.now(timezone.utc)
        self.runtime_keywords = _normalize_keywords(keywords or [])
        relevance_threshold = await _load_relevance_threshold(db)

        try:
            items = await self.crawl()
            stats.total_found = len(items)
            stats.source_reports = list(getattr(self, "source_reports", []) or [])
            source_error_count = sum(1 for report in stats.source_reports if report.get("status") == "error")
            stats.errors += source_error_count
            stats.error_messages.extend(
                str(report.get("error"))
                for report in stats.source_reports
                if report.get("status") == "error" and report.get("error")
            )
            logger.info("[%s] 爬取到 %d 条原始数据", self.name, len(items))
        except Exception as e:
            logger.error("[%s] 爬取失败: %s", self.name, e)
            stats.errors += 1
            stats.error_messages.append(str(e))
            stats.finished_at = datetime.now(timezone.utc)
            await self.close()
            return stats

        seen_urls: set[str] = set()
        seen_titles: set[tuple[str, str]] = set()
        for item in items:
            try:
                source_name = _item_source_name(item)
                _increment(stats.raw_by_source, source_name)
                url_key = (item.source_url or "").strip().lower()
                title_key = (
                    item.category or self.category,
                    " ".join((item.title or "").split()).lower(),
                )
                if (url_key and url_key in seen_urls) or title_key in seen_titles:
                    stats.duplicates_skipped += 1
                    _increment(stats.duplicate_by_source, source_name)
                    continue
                if url_key:
                    seen_urls.add(url_key)
                seen_titles.add(title_key)

                # 去重
                if await self._check_duplicate(db, item.source_url, item.title):
                    stats.duplicates_skipped += 1
                    _increment(stats.duplicate_by_source, source_name)
                    continue

                # 相关度评分
                if keywords and item.relevance_score is None:
                    item.relevance_score = self._calculate_relevance(item, keywords)
                    matched_keywords = self._match_keywords(item, keywords)
                    if matched_keywords:
                        item.extra_data = {
                            **(item.extra_data or {}),
                            "matched_keywords": matched_keywords[:10],
                        }

                if (
                    keywords
                    and item.relevance_score is not None
                    and item.relevance_score < relevance_threshold
                ):
                    stats.low_score_discarded += 1
                    _increment(stats.discarded_by_source, source_name)
                    continue

                # 生成摘要（如果还没有）
                if not item.summary and item.content:
                    item.summary = item.content[:100].strip() + ("..." if len(item.content) > 100 else "")

                await persist_crawler_result(db, item, self.category)
                stats.new_saved += 1
                _increment(stats.saved_by_source, source_name)
                _record_item_quality(stats, item, self.category)
                _record_source_latest(stats, source_name, item)

            except Exception as e:
                logger.warning("[%s] 处理单条数据失败: %s", self.name, e)
                stats.errors += 1
                stats.error_messages.append(str(e))

        stats.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[%s] 完成: 发现 %d, 新增 %d, 重复 %d, 错误 %d",
            self.name, stats.total_found, stats.new_saved,
            stats.duplicates_skipped, stats.errors,
        )
        await self.close()
        return stats


def _normalize_keywords(keywords: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        kw = str(keyword).strip()
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(kw)
    return result


def _origin_key(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}"


def _policy_interval_seconds(source_policy: dict[str, Any] | None) -> float:
    policy = normalize_crawl_policy(source_policy)
    explicit = float(policy.get("min_interval_seconds") or 0)
    per_minute = int(policy.get("max_requests_per_minute") or 0)
    rate_interval = 60.0 / per_minute if per_minute > 0 else 0.0
    return max(float(CRAWLER_MIN_REQUEST_INTERVAL), explicit, rate_interval)


def _extract_feed_or_sitemap_urls(text: str, origin: str) -> list[str]:
    if not text:
        return []
    urls: list[str] = []
    for raw in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text, flags=re.IGNORECASE):
        url = urljoin(origin, raw.strip())
        if url.startswith(("http://", "https://")):
            urls.append(url)
    for raw in re.findall(
        r"<link[^>]+(?:type=['\"]application/(?:rss|atom)\+xml['\"][^>]+href=['\"]([^'\"]+)['\"]|href=['\"]([^'\"]+)['\"][^>]+type=['\"]application/(?:rss|atom)\+xml['\"])",
        text,
        flags=re.IGNORECASE,
    ):
        href = raw[0] or raw[1]
        url = urljoin(origin, href.strip())
        if url.startswith(("http://", "https://")):
            urls.append(url)
    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _increment(bucket: dict[str, int], key: str, amount: int = 1) -> None:
    bucket[key] = int(bucket.get(key, 0)) + amount


def _item_source_name(item: CrawlResult) -> str:
    return (item.source or (item.extra_data or {}).get("source") or "未标注来源")[:200]


def _record_item_quality(stats: CrawlStats, item: CrawlResult, default_category: str) -> None:
    quality = stats.data_quality
    quality["saved_items"] = int(quality.get("saved_items", 0)) + 1
    if item.source_url:
        quality["with_source_url"] = int(quality.get("with_source_url", 0)) + 1
    if item.published_at:
        quality["with_published_at"] = int(quality.get("with_published_at", 0)) + 1
    if item.summary or item.content:
        quality["with_summary_or_content"] = int(quality.get("with_summary_or_content", 0)) + 1
    if item.relevance_score is not None:
        quality["with_relevance_score"] = int(quality.get("with_relevance_score", 0)) + 1

    category = item.category or default_category
    if category == "bidding":
        structured = _structured_fields(item)
        if structured.get("amount_wan"):
            quality["with_amount"] = int(quality.get("with_amount", 0)) + 1
        if structured.get("buyer"):
            quality["with_buyer"] = int(quality.get("with_buyer", 0)) + 1
        if structured.get("notice_type"):
            quality["with_notice_type"] = int(quality.get("with_notice_type", 0)) + 1


def _record_source_latest(stats: CrawlStats, source_name: str, item: CrawlResult) -> None:
    current = stats.latest_by_source.get(source_name)
    current_date = _cursor_date(current)
    item_date = item.published_at or date.min
    if current and current_date >= item_date:
        return
    stats.latest_by_source[source_name] = {
        "title": (item.title or "")[:200],
        "source_url": (item.source_url or "")[:500],
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": item.relevance_score,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _cursor_date(value: dict[str, Any] | None) -> date:
    if not value:
        return date.min
    raw = value.get("published_at")
    if not raw:
        return date.min
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return date.min


async def _load_relevance_threshold(db: AsyncSession) -> float:
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    if not row:
        return float(CRAWLER_RELEVANCE_THRESHOLD)
    return float(row.relevance_threshold)


async def persist_crawler_result(
    db: AsyncSession,
    item: CrawlResult,
    default_category: str,
) -> CrawlerItem:
    """Persist one crawler result and its first-class evidence/event records."""

    structured = _structured_fields(item)
    db_item = CrawlerItem(
        category=item.category or default_category,
        title=item.title[:500],
        content=item.content,
        summary=item.summary,
        source=item.source[:200] if item.source else None,
        source_url=item.source_url[:500] if item.source_url else None,
        published_at=item.published_at,
        relevance_score=item.relevance_score,
        amount_wan=structured["amount_wan"],
        buyer=structured["buyer"],
        region=structured["region"],
        notice_type=structured["notice_type"],
        matched_keywords=structured["matched_keywords"],
        extra_data=item.extra_data or None,
    )
    db.add(db_item)
    await db.flush()
    _add_crawler_evidence(db, db_item)
    return db_item


def _structured_fields(item: CrawlResult) -> dict[str, Any]:
    extra = item.extra_data or {}
    return {
        "amount_wan": _amount_from_extra_or_text(extra, " ".join([item.summary or "", item.content or "", item.title or ""])),
        "buyer": _clean_text(extra.get("buyer") or extra.get("customer") or extra.get("purchaser"), 200),
        "region": _clean_text(extra.get("location") or extra.get("region") or extra.get("area"), 100),
        "notice_type": _notice_type_from_extra(extra),
        "matched_keywords": _matched_keywords_from_extra(extra),
    }


def _add_crawler_evidence(db: AsyncSession, item: CrawlerItem) -> None:
    evidence_id = f"EV-{item.category.upper()}-{item.id}"
    flags: list[str] = []
    if not item.source_url:
        flags.append("missing_source_url")
    if not item.published_at:
        flags.append("missing_published_at")
    if item.category == "bidding" and not item.amount_wan:
        flags.append("missing_amount")

    data = {
        "amount_wan": item.amount_wan,
        "buyer": item.buyer,
        "region": item.region,
        "notice_type": item.notice_type,
        "matched_keywords": item.matched_keywords or [],
        "relevance_score": item.relevance_score,
    }
    confidence = 0.5
    if item.relevance_score is not None:
        confidence = max(0.0, min(float(item.relevance_score) / 100, 1.0))

    db.add(EvidenceRecord(
        evidence_id=evidence_id,
        source=item.source,
        source_type=(item.extra_data or {}).get("source_type") or item.category,
        category=item.category,
        title=item.title,
        source_url=item.source_url,
        record_type="crawler_item",
        record_id=item.id,
        query_summary=f"{item.category} 采集入库：{item.title[:160]}",
        data=data,
        confidence=confidence,
        data_quality_flags=flags,
        event_time=_published_datetime(item.published_at),
    ))
    db.add(IntelligenceEvent(
        event_type="item_collected",
        category=item.category,
        subject=item.title[:500],
        crawler_item_id=item.id,
        evidence_id=evidence_id,
        event_time=_published_datetime(item.published_at),
        payload=data,
    ))


