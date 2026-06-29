"""Utility helpers for the bidding crawler."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ScheduleConfig
from .base import CrawlResult, CrawlStats


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
