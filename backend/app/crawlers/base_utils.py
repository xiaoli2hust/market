"""Shared parsing helpers for crawler runtime."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


def _amount_from_extra_or_text(extra: dict[str, Any], text: str) -> float | None:
    for key in ("amount_wan", "bid_amount", "bidamount", "budget", "amount"):
        amount = _parse_amount_to_wan(extra.get(key))
        if amount > 0:
            return round(amount, 4)
    amount = _parse_labeled_amount_to_wan(text)
    return round(amount, 4) if amount > 0 else None


def _parse_amount_to_wan(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)(\s*(亿元|亿|万元|万|元))?", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(3) or "").strip()
    if unit in {"亿元", "亿"}:
        return amount * 10000
    if unit == "元":
        return amount / 10000
    return amount


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
        if match:
            return _parse_amount_to_wan("".join(match.groups()))
    return 0.0


def _matched_keywords_from_extra(extra: dict[str, Any]) -> list[str] | None:
    raw_values = [extra.get("matched_keywords"), extra.get("keywords"), extra.get("query_keyword")]
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
            if not part or len(part) > 24:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(part)
    return result[:12] or None


def _notice_type_from_extra(extra: dict[str, Any]) -> str | None:
    direct = _clean_text(extra.get("notice_type"), 80)
    if direct:
        return direct
    text = " ".join(str(extra.get(key) or "") for key in ("subtype", "channel", "basic_class"))
    for pattern in (
        "公开招标", "招标公告", "竞争性磋商", "询价", "单一来源", "采购意向",
        "更正公告", "中标结果", "成交结果", "候选人公示", "调研公告", "废标", "流标",
    ):
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
    return _clean_text(text, 80)


def _clean_text(value: Any, limit: int) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else None


def _published_datetime(value: date | None) -> datetime | None:
    if not value:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _decode_response_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _retry_after_seconds(value: str | None, attempt: int) -> float:
    fallback = 1.5 * (attempt + 1)
    if not value:
        return fallback
    text = str(value).strip()
    if text.isdigit():
        return min(max(float(text), fallback), 60.0)
    try:
        retry_at = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return fallback
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    seconds = (retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
    return min(max(seconds, fallback), 60.0)


def _looks_like_js_challenge(text: str) -> bool:
    challenge_markers = (
        "__jsl_clearance_s",
        "location.href=location.pathname+location.search",
        "正在进行安全检测",
        "浏览器安全检查",
    )
    return any(marker in text for marker in challenge_markers)
