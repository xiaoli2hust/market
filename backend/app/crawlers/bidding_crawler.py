"""结构化标讯 API 爬虫。

直接调用已配置数据源的 data-preview API，
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
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DingtalkConfig, ScheduleConfig
from ..secret_store import decrypt_secret
from .base import BaseCrawler, CrawlResult, CrawlStats, persist_crawler_result, _record_source_latest
from .config import CRAWLER_MAX_ITEMS_PER_SOURCE
from .intelligence_agent import build_intelligence_profile

logger = logging.getLogger(__name__)

# API 配置
_JIANYU_API_BASE = "https://customer.jianyu360.com"
_JIANYU_DATA_API = "/private/keydatademo/{key}"
_JIANYU_OPTION_API = "/private/keydataoption/{key}"


class JianyuBiddingCrawler(BaseCrawler):
    """结构化标讯 API 爬虫。"""

    name = "bidding"
    category = "bidding"

    def __init__(self, sources: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._api_key: str = ""
        self._username: str = ""
        self._password: str = ""
        self._customer_name: str = ""
        self._runtime_keywords: list[str] = []
        self.sources = sources or []

    async def _load_config(self, db: AsyncSession) -> None:
        """从数据库加载结构化标讯配置。"""
        row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
        if not row:
            return
        self._username = row.jianyu_username or ""
        self._password = decrypt_secret(row.jianyu_password)
        self._api_key = decrypt_secret(row.jianyu_api_key)

    async def crawl(self, db: AsyncSession | None = None) -> list[CrawlResult]:
        """调用 API 获取标讯数据。"""
        if db:
            await self._load_config(db)

        results: list[CrawlResult] = []

        try:
            if not self._api_key and self._username and self._password:
                self._api_key = await self._discover_api_key(self._username, self._password)

            if not self._api_key:
                logger.warning("[bidding] 结构化标讯数据 key 未配置，跳过")
                self.source_reports.append({
                    "name": "结构化标讯数据",
                    "url": _JIANYU_API_BASE,
                    "type": "authorized_api",
                    "crawl_policy": {"risk_level": "authorized_api"},
                    "status": "skipped",
                    "found": 0,
                    "error": "结构化标讯数据 key 未配置",
                })
            else:
                # 调用 API（同步，API 很快）
                items, customer_name = await self._fetch_data(self._api_key)
                self._customer_name = customer_name

                for item in items:
                    result = self._to_crawl_result(item)
                    if result:
                        results.append(result)

                self.source_reports.append({
                    "name": "结构化标讯数据",
                    "url": _JIANYU_API_BASE,
                    "type": "authorized_api",
                    "crawl_policy": {"risk_level": "authorized_api"},
                    "status": "ok",
                    "found": len(results),
                    "customer": "已配置",
                })
                logger.info("[bidding] API 返回 %d 条标讯 (客户: %s)", len(results), customer_name)

        except Exception as e:
            self.source_reports.append({
                "name": "结构化标讯数据",
                "url": _JIANYU_API_BASE,
                "type": "authorized_api",
                "crawl_policy": {"risk_level": "authorized_api"},
                "status": "error",
                "found": 0,
                "error": str(e),
            })
            logger.error("[bidding] API 调用失败: %s", e, exc_info=True)

        for source in self.sources:
            try:
                public_items = await self._crawl_public_source(source)
                results.extend(public_items)
                self.source_reports.append({
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "type": source.get("type") or (source.get("selectors") or {}).get("type") or "official_site",
                    "crawl_policy": source.get("crawl_policy"),
                    "status": "ok",
                    "found": len(public_items),
                    "compliance": "robots+rate_limit",
                })
                logger.info("[bidding] %s: 公开源获取 %d 条", source.get("name"), len(public_items))
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
                logger.warning("[bidding] %s 公开源采集失败: %s", source.get("name"), e)

        return results

    async def _crawl_public_source(self, source: dict[str, Any]) -> list[CrawlResult]:
        source_type = source.get("type") or (source.get("selectors") or {}).get("type") or "official_site"
        if source_type == "direct_pages":
            return await self._crawl_public_direct_pages(source)
        if source_type in {"api", "browser"}:
            return []

        html = await self._safe_get_text(
            source["url"],
            source_name=source.get("name"),
            source_policy=source.get("crawl_policy"),
        )
        soup = BeautifulSoup(html, "lxml")
        selectors = source.get("selectors") or {}
        list_selector = selectors.get("list") or "a"
        nodes = soup.select(list_selector)
        if not nodes and list_selector != "a":
            nodes = soup.select("a")

        results: list[CrawlResult] = []
        for node in nodes[: CRAWLER_MAX_ITEMS_PER_SOURCE * 10]:
            parsed = self._parse_public_node(node, source, selectors)
            if parsed is None:
                continue
            parsed = await self._enrich_public_detail(parsed, source)
            results.append(parsed)
            if len(results) >= CRAWLER_MAX_ITEMS_PER_SOURCE:
                break
        return _dedupe_results(results)

    async def _enrich_public_detail(self, item: CrawlResult, source: dict[str, Any]) -> CrawlResult:
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
                _text_of_first(soup, "h1, .title, .article-title, .detail-title")
                or (soup.title.get_text(" ", strip=True) if soup.title else "")
                or item.title
            )
            content = _text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, article, body")
            title = re.sub(r"\s+", " ", title or item.title).strip()
            content = re.sub(r"\s+", " ", content or item.content or title).strip()
            if not _looks_like_public_bidding_notice(title, content):
                return item

            extra = dict(item.extra_data or {})
            amount_wan, amount_text, amount_source = _extract_amount_wan({}, title, content)
            if amount_wan > 0:
                extra["amount_wan"] = round(amount_wan, 4)
                extra["amount_text"] = amount_text
                extra["amount_source"] = f"detail.{amount_source}"
            notice_type = _notice_type(title, content, "")
            matched_keywords = _matched_public_bidding_keywords(title, content, self._runtime_keywords)
            extra.update({
                "detail_fetched": True,
                "notice_type": notice_type,
                "matched_keywords": matched_keywords,
            })
            extra["agent_profile"] = build_intelligence_profile(
                kind="bidding",
                title=title,
                content=content,
                source=item.source,
                source_url=item.source_url,
                matched_keywords=matched_keywords[:12],
                extra=extra,
            )
            item.title = title[:500]
            item.content = content[:4000]
            item.published_at = _parse_public_date(f"{content} {item.source_url}") or item.published_at
            item.relevance_score = self._score_item(title, content, " ".join(matched_keywords))
            summary_parts = [f"来源: {item.source}", f"类型: {notice_type}"]
            if amount_wan > 0:
                summary_parts.append(f"金额: {_format_amount_wan(amount_wan)}")
            item.summary = " | ".join(summary_parts)[:200]
            item.extra_data = extra
        except Exception as exc:  # noqa: BLE001
            extra = dict(item.extra_data or {})
            extra["detail_fetch_error"] = str(exc)[:300]
            item.extra_data = extra
        return item

    async def _crawl_public_direct_pages(self, source: dict[str, Any]) -> list[CrawlResult]:
        results: list[CrawlResult] = []
        for page in (source.get("pages") or [])[:CRAWLER_MAX_ITEMS_PER_SOURCE]:
            html = await self._safe_get_text(
                page["url"],
                source_name=page.get("name") or source.get("name"),
                source_policy=source.get("crawl_policy"),
            )
            soup = BeautifulSoup(html, "lxml")
            title = (
                page.get("title")
                or _text_of_first(soup, "h1, .title, .article-title")
                or (soup.title.get_text(" ", strip=True) if soup.title else "")
            )
            content = _text_of_first(soup, ".TRS_Editor, .article-content, .content, .detail, .main, body")
            parsed = self._build_public_result(
                title=title,
                content=content or title,
                link=page["url"],
                source=source,
                pub_date=_parse_public_date(f"{content} {page['url']}"),
            )
            if parsed is not None:
                results.append(parsed)
        return _dedupe_results(results)

    def _parse_public_node(self, node: Any, source: dict[str, Any], selectors: dict[str, Any]) -> CrawlResult | None:
        title_el = _first_select(node, selectors.get("title") or "a")
        if title_el is None:
            title_el = node if getattr(node, "name", "") == "a" else node.select_one("a")
        if title_el is None:
            return None

        title = title_el.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title or "").strip()
        if _is_navigation_bidding_title(title):
            return None

        base_url = source.get("base_url") or source.get("url") or ""
        link = _extract_public_link(node, title_el, base_url, selectors)
        if not link or link.lower().startswith(("javascript:", "#")):
            return None

        content = node.get_text(" ", strip=True)
        content = re.sub(r"\s+", " ", content or title).strip()
        pub_date = _parse_public_date(f"{content} {link}")
        return self._build_public_result(
            title=title,
            content=content,
            link=link,
            source=source,
            pub_date=pub_date,
        )

    def _build_public_result(
        self,
        *,
        title: str,
        content: str,
        link: str,
        source: dict[str, Any],
        pub_date: date | None,
    ) -> CrawlResult | None:
        title = re.sub(r"\s+", " ", title or "").strip()
        content = re.sub(r"\s+", " ", content or title).strip()
        if not _looks_like_public_bidding_notice(title, content):
            return None

        score = self._score_item(title, content, "")
        if score <= 0:
            return None

        amount_wan, amount_text, amount_source = _extract_amount_wan({}, title, content)
        notice_type = _notice_type(title, content, "")
        matched_keywords = _matched_public_bidding_keywords(title, content, self._runtime_keywords)
        source_name = source.get("name") or "公开标讯源"
        extra = {
            "source": source_name,
            "source_type": "official_public_bidding",
            "notice_type": notice_type,
            "amount_wan": round(amount_wan, 4) if amount_wan > 0 else None,
            "amount_text": amount_text,
            "amount_source": amount_source,
            "keywords": "、".join(matched_keywords),
            "matched_keywords": matched_keywords,
            "review_state": "matched",
        }
        extra["agent_profile"] = build_intelligence_profile(
            kind="bidding",
            title=title,
            content=content,
            source=source_name,
            source_url=link,
            matched_keywords=matched_keywords[:12],
            extra=extra,
        )

        summary_parts = [f"来源: {source_name}", f"类型: {notice_type}"]
        if amount_wan > 0:
            summary_parts.append(f"金额: {_format_amount_wan(amount_wan)}")
        return CrawlResult(
            category="bidding",
            title=title[:500],
            source=source_name,
            source_url=link[:500],
            content=content[:2000],
            summary=" | ".join(summary_parts)[:200],
            published_at=pub_date,
            relevance_score=score,
            extra_data=extra,
        )

    async def _discover_api_key(self, username: str, password: str) -> str:
        """通过数据源账号登录平台，发现启用规则的结构化数据 key。"""

        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            login_resp = await client.post(_JIANYU_API_BASE + "/", data={"email": username, "pwd": password})
            if login_resp.status_code != 200:
                raise RuntimeError(f"结构化标讯数据源登录 HTTP {login_resp.status_code}")
            login_data = login_resp.json()
            if not login_data.get("checked"):
                raise RuntimeError("结构化标讯数据源登录失败，请检查账号密码")

            customer_id = str(login_data.get("id") or "")
            index_resp = await client.get(f"{_JIANYU_API_BASE}/client/index", params={"id": customer_id})
            index_resp.raise_for_status()
            depart_ids = re.findall(r'"_id":"([a-f0-9]{24})".*?"s_userid":"([a-f0-9]{24})"', index_resp.text)
            if not depart_ids:
                raise RuntimeError("账号下未发现部门规则")

            for depart_id, user_id in depart_ids:
                list_resp = await client.post(
                    _JIANYU_API_BASE + "/client/cuser/rule/list",
                    data={"draw": "1", "start": "0", "length": "50", "ids": f"{depart_id},{user_id}"},
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
                list_resp.raise_for_status()
                for rule in list_resp.json().get("data", []):
                    if int(rule.get("i_isuse") or 0) != 1:
                        continue
                    key = str(rule.get("s_dataid") or "").strip()
                    if key:
                        logger.info("[bidding] 自动发现启用规则: %s", rule.get("s_name") or rule.get("_id"))
                        return key

        raise RuntimeError("账号下未发现启用规则的结构化数据 key")

    async def _fetch_data(self, api_key: str) -> tuple[list[dict[str, Any]], str]:
        """调用结构化标讯 data-preview API。"""
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

        # 提取金额：结构化字段为空时，从正文中的预算/最高限价/中标金额兜底挖取。
        amount_wan, amount_text, amount_source = _extract_amount_wan(item, title, item.get("detail", ""))
        bid_amount = amount_wan if amount_wan > 0 else item.get("bidamount", "")

        # 提取发布时间
        pub_time = ""
        come_in_time = item.get("comeintime", 0)
        if come_in_time:
            try:
                pub_time = datetime.fromtimestamp(come_in_time).strftime("%Y-%m-%d")
            except (OSError, OverflowError, TypeError, ValueError):
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
        if amount_wan > 0:
            summary_parts.append(f"金额: {_format_amount_wan(amount_wan)}")
        notice_type = _notice_type(subtype, channel, basic_class)
        if notice_type:
            summary_parts.append(f"类型: {notice_type}")

        summary = " | ".join(summary_parts) if summary_parts else title[:100]

        # 额外数据
        extra = {
            "source": "结构化标讯数据",
            "customer": "已配置",
            "buyer": buyer,
            "buyer_person": buyer_person,
            "buyer_tel": buyer_tel,
            "winner": winner,
            "bid_amount": bid_amount,
            "amount_wan": round(amount_wan, 4) if amount_wan > 0 else None,
            "amount_text": amount_text,
            "amount_source": amount_source,
            "location": location,
            "subtype": subtype,
            "channel": channel,
            "basic_class": basic_class,
            "project_code": project_code,
            "project_name": project_name,
            "keywords": show_key,
            "autoid": item.get("autoid", ""),
        }
        matched_keywords = [kw.strip() for kw in re.split(r"[,，、\s]+", show_key) if kw.strip()]
        extra["agent_profile"] = build_intelligence_profile(
            kind="bidding",
            title=title,
            content=detail,
            source="结构化标讯数据",
            source_url=href,
            matched_keywords=matched_keywords[:12],
            extra=extra,
        )

        # 解析发布日期
        pub_date = None
        if pub_time:
            try:
                pub_date = date.fromisoformat(pub_time[:10])
            except ValueError:
                pass

        return CrawlResult(
            category="bidding",
            title=title[:500],
            source="标讯数据",
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

        runtime_hits = sum(1 for kw in self._runtime_keywords if _contains_business_keyword(text, kw))
        if runtime_hits >= 5:
            max_score = max(max_score, 90.0)
        elif runtime_hits >= 3:
            max_score = max(max_score, 70.0)
        elif runtime_hits >= 2:
            max_score = max(max_score, 50.0)
        elif runtime_hits >= 1:
            max_score = max(max_score, 30.0)

        for direction, kws in JIANYU_BUSINESS_KEYWORDS.items():
            hits = sum(1 for kw in kws if _contains_business_keyword(text, kw))
            if hits >= 5:
                score = 90.0
            elif hits >= 3:
                score = 70.0
            elif hits >= 2:
                score = 50.0
            elif hits >= 1:
                score = 30.0
            else:
                score = 0.0
            max_score = max(max_score, score)

        return max_score

    async def run(self, db: AsyncSession, keywords: list[str] | None = None) -> CrawlStats:
        """重写 run 方法。"""
        stats = CrawlStats(crawler_name=self.name)
        stats.started_at = datetime.now(timezone.utc)
        self._runtime_keywords = _normalize_keywords(keywords or [])
        relevance_threshold = await _load_relevance_threshold(db)

        try:
            items = await self.crawl(db=db)
            stats.total_found = len(items)
            stats.source_reports = list(self.source_reports)
            source_error_count = sum(1 for report in stats.source_reports if report.get("status") == "error")
            stats.errors += source_error_count
            stats.error_messages.extend(
                str(report.get("error"))
                for report in stats.source_reports
                if report.get("status") == "error" and report.get("error")
            )
            logger.info("[bidding] API 获取 %d 条标讯", len(items))
        except Exception as e:
            logger.error("[bidding] 爬取失败: %s", e)
            stats.errors += 1
            stats.error_messages.append(str(e))
            stats.finished_at = datetime.now(timezone.utc)
            await self.close()
            return stats

        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        for item in items:
            try:
                source_name = _item_source_name(item)
                _increment(stats.raw_by_source, source_name)
                url_key = (item.source_url or "").strip().lower()
                title_key = " ".join((item.title or "").split()).lower()
                if (url_key and url_key in seen_urls) or title_key in seen_titles:
                    stats.duplicates_skipped += 1
                    _increment(stats.duplicate_by_source, source_name)
                    continue
                if url_key:
                    seen_urls.add(url_key)
                if title_key:
                    seen_titles.add(title_key)

                # 去重
                source_url = item.source_url or item.title
                if await self._check_duplicate(db, source_url, item.title):
                    stats.duplicates_skipped += 1
                    _increment(stats.duplicate_by_source, source_name)
                    continue

                # 低分过滤
                if item.relevance_score is not None and item.relevance_score < relevance_threshold:
                    stats.low_score_discarded += 1
                    _increment(stats.discarded_by_source, source_name)
                    continue

                await persist_crawler_result(db, item, self.category)
                stats.new_saved += 1
                _increment(stats.saved_by_source, source_name)
                _record_bidding_quality(stats, item)
                _record_source_latest(stats, source_name, item)

            except Exception as e:
                logger.warning("[bidding] 处理单条失败: %s", e)
                stats.errors += 1
                stats.error_messages.append(str(e))

        stats.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[bidding] 完成: 发现 %d, 新增 %d, 重复 %d, 低分 %d, 错误 %d",
            stats.total_found, stats.new_saved,
            stats.duplicates_skipped, stats.low_score_discarded, stats.errors,
        )
        await self.close()
        return stats


def _notice_type(subtype: str, channel: str, basic_class: str) -> str:
    text = f"{subtype} {channel} {basic_class}"
    patterns = [
        "公开招标",
        "招标公告",
        "竞争性磋商",
        "询价",
        "单一来源",
        "采购意向",
        "更正公告",
        "中标结果",
        "成交结果",
        "候选人公示",
        "调研公告",
        "废标",
        "流标",
    ]
    for pattern in patterns:
        if pattern in text:
            return pattern
    if "中标" in text:
        return "中标结果"
    if "成交" in text:
        return "成交结果"
    if "招标" in text:
        return "招标公告"
    if "公示" in text:
        return "公示"
    return "公告"


def _extract_amount_wan(item: dict[str, Any], title: str, detail: str) -> tuple[float, str, str]:
    """从结构化字段和公告正文抽取金额，统一换算为万元。"""

    field_candidates = [
        "bidamount",
        "budget",
        "budgetamount",
        "budgetAmount",
        "amount",
        "money",
        "price",
        "limitprice",
        "limitPrice",
        "projectbudget",
        "projectBudget",
    ]
    for field in field_candidates:
        value = item.get(field)
        amount = _amount_to_wan(value, default_unit="万")
        if amount > 0:
            return amount, str(value), field

    for package in item.get("com_package") or []:
        if not isinstance(package, dict):
            continue
        for field in field_candidates:
            value = package.get(field)
            amount = _amount_to_wan(value, default_unit="万")
            if amount > 0:
                return amount, str(value), f"com_package.{field}"

    text = " ".join(
        str(part or "")
        for part in [
            title,
            item.get("summary"),
            item.get("content"),
            detail,
            item.get("bodyContent"),
            item.get("noticecontent"),
        ]
    )
    amount, raw = _amount_from_text(text)
    if amount > 0:
        return amount, raw, "content"
    return 0.0, "", ""


def _amount_from_text(text: str) -> tuple[float, str]:
    cleaned = re.sub(r"\s+", "", str(text or "").replace(",", ""))
    if not cleaned:
        return 0.0, ""
    patterns = [
        r"(?:预算金额|预算价|项目预算|采购预算|最高限价|控制价|招标控制价|中标金额|成交金额|中标价|成交价|报价金额|合同金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
        r"(?:人民币|金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        raw = "".join(match.groups())
        amount = _amount_to_wan(raw)
        if amount > 0:
            return amount, raw
    return 0.0, ""


def _amount_to_wan(value: Any, *, default_unit: str | None = None) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)(\s*(亿元|亿|万元|万|元))?", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(3) or default_unit or "").strip()
    if unit in {"亿元", "亿"}:
        return amount * 10000
    if unit == "元":
        return amount / 10000
    return amount


def _format_amount_wan(amount: float) -> str:
    if amount >= 10000:
        return f"{amount / 10000:.2f}亿元"
    if amount >= 100:
        return f"{amount:.1f}万元"
    return f"{amount:.2f}万元"


def _first_select(node: Any, selectors: str) -> Any | None:
    for selector in selectors.split(","):
        selector = selector.strip()
        if not selector:
            continue
        found = node.select_one(selector)
        if found:
            return found
    return None


def _extract_public_link(node: Any, title_el: Any, base_url: str, selectors: dict[str, Any]) -> str:
    link_selector = selectors.get("link") or "a@href"
    href = ""
    if "@" in link_selector:
        tag_selector, attr = link_selector.split("@", 1)
        tag = node.select_one(tag_selector)
        if tag:
            href = str(tag.get(attr) or "")
    if not href:
        if getattr(title_el, "name", "") == "a":
            href = str(title_el.get("href") or "")
        else:
            tag = title_el.select_one("a") or node.select_one("a")
            if tag:
                href = str(tag.get("href") or "")
    if not href:
        return ""
    return urljoin(base_url, href)


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


def _parse_public_date(text: str) -> date | None:
    patterns = [
        r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])",
        r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if not match:
            continue
        try:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day)).date()
        except ValueError:
            return None
    return None


def _is_navigation_bidding_title(title: str) -> bool:
    value = re.sub(r"\s+", "", title or "")
    if len(value) < 6:
        return True
    navigation_words = {
        "首页", "采购公告", "招标公告", "非招标公告", "中标公告", "成交公告",
        "结果公告", "更正公告", "通知公告", "政策法规", "服务指南", "注册指南",
        "下载中心", "在线培训", "联系我们", "更多", "搜索",
    }
    return value in navigation_words


def _looks_like_public_bidding_notice(title: str, content: str) -> bool:
    text = f"{title} {content}"
    notice_terms = (
        "采购项目", "招标公告", "采购公告", "公开招标", "竞争性磋商", "竞争性谈判",
        "询价", "单一来源", "比选", "遴选", "中标", "成交", "候选人公示",
        "结果公告", "采购意向", "框架协议", "项目招标", "服务采购",
    )
    return any(term in text for term in notice_terms)


def _matched_public_bidding_keywords(title: str, content: str, runtime_keywords: list[str]) -> list[str]:
    from .config import JIANYU_BUSINESS_KEYWORDS

    text = f"{title} {content}".lower()
    result: list[str] = []
    for keyword in runtime_keywords:
        if _contains_business_keyword(text, keyword) and keyword not in result:
            result.append(keyword)
    for keywords in JIANYU_BUSINESS_KEYWORDS.values():
        for keyword in keywords:
            if _contains_business_keyword(text, keyword) and keyword not in result:
                result.append(keyword)
    return result[:12]


def _contains_business_keyword(text: str, keyword: str) -> bool:
    value = str(keyword or "").strip()
    if not value:
        return False
    lowered = text.lower()
    needle = value.lower()
    if re.fullmatch(r"[a-z0-9]{1,4}", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) is not None
    return needle in lowered


def _dedupe_results(items: list[CrawlResult]) -> list[CrawlResult]:
    result: list[CrawlResult] = []
    seen: set[str] = set()
    for item in items:
        key = (item.source_url or item.title).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


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


def _increment(bucket: dict[str, int], key: str, amount: int = 1) -> None:
    bucket[key] = int(bucket.get(key, 0)) + amount


def _item_source_name(item: CrawlResult) -> str:
    return (item.source or (item.extra_data or {}).get("source") or "未标注来源")[:200]


def _record_bidding_quality(stats: CrawlStats, item: CrawlResult) -> None:
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

    extra = item.extra_data or {}
    if extra.get("amount_wan"):
        quality["with_amount"] = int(quality.get("with_amount", 0)) + 1
    if extra.get("buyer"):
        quality["with_buyer"] = int(quality.get("with_buyer", 0)) + 1
    if extra.get("notice_type"):
        quality["with_notice_type"] = int(quality.get("with_notice_type", 0)) + 1


async def _load_relevance_threshold(db: AsyncSession) -> float:
    row = (await db.execute(select(ScheduleConfig).limit(1))).scalar_one_or_none()
    if not row:
        return 30.0
    return float(row.relevance_threshold)
