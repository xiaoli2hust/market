from __future__ import annotations

import re
from typing import Any

from ..models import CrawlerItem, CrawlerRunLog


def _parse_amount_to_wan(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    if "亿" in text:
        return amount * 10000
    if "元" in text and "万元" not in text and "万" not in text:
        return amount / 10000
    return amount


def _item_amount_wan(item: CrawlerItem) -> float:
    if item.amount_wan and item.amount_wan > 0:
        return float(item.amount_wan)
    extra = item.extra_data or {}
    for key in ("amount_wan", "bid_amount"):
        amount = _parse_amount_to_wan(extra.get(key))
        if amount > 0:
            return amount
    amount = _parse_labeled_amount_to_wan(" ".join([item.summary or "", item.content or "", item.title or ""]))
    return amount


def _item_region(item: CrawlerItem) -> str | None:
    if item.region:
        return str(item.region).strip("- ") or None
    extra = item.extra_data or {}
    location = str(extra.get("location") or extra.get("region") or extra.get("area") or "").strip("- ")
    return location or None


def _item_notice_type(item: CrawlerItem) -> str:
    if item.notice_type:
        return item.notice_type
    return _notice_type(item.extra_data or {})


def _item_matched_keywords(item: CrawlerItem) -> list[str]:
    raw = item.matched_keywords
    if raw:
        values = raw if isinstance(raw, list) else [raw]
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            keyword = str(value or "").strip()
            if not keyword or len(keyword) > 24:
                continue
            key = keyword.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(keyword)
        if result:
            return result
    return _matched_keywords(item.extra_data or {})


def _parse_labeled_amount_to_wan(text: str) -> float:
    cleaned = re.sub(r"\s+", "", str(text or "").replace(",", ""))
    if not cleaned:
        return 0.0
    patterns = [
        r"(?:预算金额|预算价|项目预算|采购预算|最高限价|控制价|招标控制价|中标金额|成交金额|中标价|成交价|报价金额|合同金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
        r"(?:人民币|金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        amount = _parse_amount_to_wan("".join(match.groups()))
        if amount > 0:
            return amount
    return 0.0


def _matched_keywords(extra: dict[str, Any]) -> list[str]:
    raw_values = [
        extra.get("matched_keywords"),
        extra.get("keywords"),
        extra.get("query_keyword"),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not raw:
            continue
        if isinstance(raw, list):
            parts = [str(part).strip() for part in raw]
        else:
            parts = [part.strip() for part in re.split(r"[,，、\s]+", str(raw)) if part.strip()]
        for part in parts:
            if len(part) > 24:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(part)
    return result


def _public_source_name(item: CrawlerItem) -> str:
    if item.category == "bidding":
        return "标讯数据"
    return item.source or "外部信号"


def _public_summary(item: CrawlerItem) -> str | None:
    if item.category != "bidding":
        return item.summary

    extra = item.extra_data or {}
    parts = []
    buyer = str(item.buyer or extra.get("buyer") or "").strip()
    winner = str(extra.get("winner") or "").strip()
    amount_wan = _item_amount_wan(item)
    notice_type = _item_notice_type(item)
    if buyer:
        parts.append(f"采购人: {buyer}")
    if winner:
        parts.append(f"中标: {winner}")
    if amount_wan > 0:
        parts.append(f"金额: {_format_amount_wan(amount_wan)}")
    if notice_type:
        parts.append(f"类型: {notice_type}")
    return " | ".join(parts) if parts else item.summary


def _notice_type(extra: dict[str, Any]) -> str:
    text = " ".join(str(extra.get(key) or "") for key in ("subtype", "channel", "basic_class"))
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


def _format_amount_wan(amount: float) -> str:
    if amount >= 10000:
        return f"{amount / 10000:.2f}亿元"
    if amount >= 100:
        return f"{amount:.1f}万元"
    return f"{amount:.2f}万元"


def _public_run_extra(row: CrawlerRunLog) -> dict[str, Any] | None:
    extra = dict(row.extra_data or {})
    if row.category != "bidding":
        return extra or None

    sanitized_reports = []
    for report in extra.get("source_reports") or []:
        if not isinstance(report, dict):
            continue
        report_url = str(report.get("url") or "")
        report_name = str(report.get("name") or "")
        is_authorized_source = "结构化标讯" in report_name or "结构化标讯" in str(report.get("diagnosis_label") or "") or "jianyu360.com" in report_url
        sanitized = {
            "source_id": report.get("source_id"),
            "name": "结构化标讯接口" if is_authorized_source else (report.get("name") or "公开标讯源"),
            "status": report.get("status"),
            "status_label": report.get("status_label"),
            "found": report.get("found", 0),
            "query_keywords": report.get("query_keywords") or [],
            "source_type": "authorized_api" if is_authorized_source else report.get("source_type"),
            "diagnosis_code": report.get("diagnosis_code"),
            "diagnosis_label": report.get("diagnosis_label"),
            "severity": report.get("severity"),
            "next_action": report.get("next_action"),
            "anti_crawl_level": report.get("anti_crawl_level"),
            "compliance": report.get("compliance"),
            "raw_count": report.get("raw_count", 0),
            "saved_count": report.get("saved_count", 0),
            "duplicate_count": report.get("duplicate_count", 0),
            "discarded_count": report.get("discarded_count", 0),
        }
        if report.get("error"):
            sanitized["error"] = report.get("error")
        sanitized_reports.append(sanitized)
    extra["source_reports"] = sanitized_reports
    return extra


def _crawler_item_to_dict(item: CrawlerItem) -> dict[str, Any]:
    extra_data = dict(item.extra_data or {})
    amount_wan = _item_amount_wan(item)
    amount_display = _format_amount_wan(amount_wan) if amount_wan > 0 else None
    matched_keywords = _item_matched_keywords(item)
    region = _item_region(item)
    notice_type = _item_notice_type(item) if item.category == "bidding" else item.notice_type
    if amount_wan > 0:
        extra_data["amount_wan"] = round(amount_wan, 4)
        extra_data["amount_display"] = amount_display
    if item.buyer:
        extra_data["buyer"] = item.buyer
    if region:
        extra_data["location"] = region
    if notice_type:
        extra_data["notice_type"] = notice_type
    if matched_keywords:
        extra_data["matched_keywords"] = matched_keywords

    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "summary": _public_summary(item),
        "source": _public_source_name(item),
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": item.relevance_score,
        "amount_wan": round(amount_wan, 4) if amount_wan > 0 else None,
        "amount_display": amount_display,
        "buyer": item.buyer,
        "region": region,
        "notice_type": notice_type,
        "matched_keywords": matched_keywords or None,
        "extra_data": extra_data or None,
        "is_pushed": item.is_pushed,
        "is_invalid": item.is_invalid,
        "invalid_reason": item.invalid_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
