"""Daily Express generation service.

Aggregates crawler_items by category, renders a beautiful newsletter-style HTML,
and stores in the daily_express table.
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrawlerItem, DailyExpress

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category config
# ---------------------------------------------------------------------------

_CATEGORY_CONFIG = {
    "bidding": {
        "label": "标讯信息",
        "color": "#C53A2C",
        "icon": "📋",
        "max_items": 10,
    },
    "news": {
        "label": "市场动态",
        "color": "#1890ff",
        "icon": "🌐",
        "max_items": 8,
    },
    "competitor": {
        "label": "竞对监控",
        "color": "#fa8c16",
        "icon": "👁",
        "max_items": 8,
    },
    "ai": {
        "label": "AI资讯",
        "color": "#722ed1",
        "icon": "🤖",
        "max_items": 6,
    },
}


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    color: #1a1714; background: #f5efe3; line-height: 1.6;
}
.express { max-width: 680px; margin: 0 auto; background: #faf6ec; }

/* Masthead */
.masthead {
    background: #1a1714; color: #faf6ec; padding: 32px 24px 24px;
    text-align: center; position: relative;
}
.masthead::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 4px; background: linear-gradient(90deg, #C53A2C, #fa8c16, #722ed1, #1890ff);
}
.masthead-badge {
    display: inline-block; font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: rgba(250,246,236,0.5);
    border: 1px solid rgba(250,246,236,0.2); padding: 4px 16px;
    margin-bottom: 12px;
}
.masthead-title {
    font-size: 32px; font-weight: 800; line-height: 1.2; margin-bottom: 8px;
}
.masthead-title .accent { color: #C53A2C; }
.masthead-date {
    font-size: 14px; color: rgba(250,246,236,0.7); margin-top: 8px;
}

/* Stats bar */
.stats-bar {
    display: flex; background: #1a1714; padding: 0;
}
.stat-cell {
    flex: 1; text-align: center; padding: 12px 8px;
    border-right: 1px solid rgba(250,246,236,0.1);
}
.stat-cell:last-child { border-right: none; }
.stat-icon { font-size: 18px; }
.stat-num {
    font-size: 22px; font-weight: 800;
    font-family: Georgia, serif;
}
.stat-label {
    font-size: 9px; color: rgba(250,246,236,0.5);
    letter-spacing: 0.1em; margin-top: 2px;
}

/* Content */
.content { padding: 0 20px; }

/* Section */
.section {
    padding: 20px 0; border-bottom: 1px dashed rgba(26,23,20,0.15);
}
.section:last-child { border-bottom: none; }
.section-head {
    display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
}
.section-icon {
    width: 28px; height: 28px; display: flex; align-items: center;
    justify-content: center; font-size: 16px;
    border-radius: 4px;
}
.section-title {
    font-size: 16px; font-weight: 700;
}
.section-count {
    font-size: 11px; color: #7a6f62; margin-left: auto;
    font-family: Georgia, serif;
}

/* Bidding cards */
.bid-card {
    background: #fff; border: 1px solid rgba(26,23,20,0.08);
    border-radius: 6px; padding: 12px 14px; margin-bottom: 8px;
    border-left: 3px solid #C53A2C;
}
.bid-title {
    font-size: 14px; font-weight: 600; color: #1a1714; margin-bottom: 6px;
    line-height: 1.4;
}
.bid-meta {
    display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: #7a6f62;
}
.bid-tag {
    display: inline-block; background: rgba(197,58,44,0.08); color: #C53A2C;
    padding: 1px 8px; border-radius: 10px; font-size: 11px;
}

/* News items */
.news-item {
    padding: 10px 0; border-bottom: 1px dashed rgba(26,23,20,0.08);
}
.news-item:last-child { border-bottom: none; }
.news-title {
    font-size: 14px; font-weight: 600; color: #1a1714; margin-bottom: 4px;
    line-height: 1.4;
}
.news-source {
    font-size: 11px; color: #7a6f62; margin-right: 8px;
}
.news-summary {
    font-size: 13px; color: #3b342d; line-height: 1.6; margin-top: 4px;
}

/* Competitor items */
.comp-group { margin-bottom: 12px; }
.comp-company {
    font-size: 13px; font-weight: 700; color: #fa8c16; margin-bottom: 6px;
    padding-bottom: 4px; border-bottom: 1px solid rgba(250,140,22,0.2);
}
.comp-item {
    display: flex; gap: 8px; padding: 6px 0;
    font-size: 13px; color: #3b342d;
}
.comp-type {
    flex-shrink: 0; font-size: 11px; padding: 1px 6px;
    border-radius: 3px; background: rgba(250,140,22,0.1); color: #fa8c16;
    height: fit-content; margin-top: 1px;
}

/* AI items */
.ai-item {
    background: #fff; border-radius: 6px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid rgba(26,23,20,0.06);
}
.ai-title {
    font-size: 14px; font-weight: 600; color: #1a1714; margin-bottom: 4px;
}
.ai-meta {
    display: flex; gap: 8px; font-size: 11px; color: #7a6f62;
}
.ai-tag {
    display: inline-block; background: rgba(114,46,209,0.08); color: #722ed1;
    padding: 1px 8px; border-radius: 10px;
}
.ai-summary {
    font-size: 13px; color: #3b342d; line-height: 1.5; margin-top: 4px;
}

/* Empty state */
.empty-section {
    text-align: center; padding: 16px; color: #7a6f62; font-size: 13px;
}

/* Footer */
.footer {
    text-align: center; padding: 20px 24px;
    border-top: 1px solid rgba(26,23,20,0.1);
    background: #f5efe3;
}
.footer-text { font-size: 11px; color: #7a6f62; letter-spacing: 0.08em; }
.footer-line { font-size: 10px; color: rgba(122,111,98,0.6); margin-top: 4px; }

@media print {
    body { background: #fff; }
}
"""


# ---------------------------------------------------------------------------
# HTML escape
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_bidding(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-section">暂无标讯数据</div>'

    cards = ""
    for item in items:
        extra = item.get("extra_data") or {}
        budget = extra.get("budget", "")
        purchaser = extra.get("purchaser", "")
        source = item.get("source") or ""

        meta_parts = []
        if source:
            meta_parts.append(f'<span>{_esc(source)}</span>')
        if budget:
            meta_parts.append(f'<span class="bid-tag">{_esc(budget)}</span>')
        if purchaser:
            meta_parts.append(f'<span>{_esc(purchaser)}</span>')

        pub_date = item.get("published_at")
        if pub_date:
            meta_parts.append(f'<span>{pub_date}</span>')

        cards += f'''<div class="bid-card">
            <div class="bid-title">{_esc(item["title"])}</div>
            <div class="bid-meta">{" &middot; ".join(meta_parts)}</div>
        </div>'''

    return cards


def _render_news(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-section">暂无市场动态</div>'

    html = ""
    for item in items:
        source = item.get("source") or ""
        summary = item.get("summary") or (item.get("content") or "")[:100]
        pub_date = item.get("published_at") or ""

        html += f'''<div class="news-item">
            <div class="news-title">{_esc(item["title"])}</div>
            <div>
                <span class="news-source">{_esc(source)}</span>
                <span style="font-size:11px;color:#aaa;">{pub_date}</span>
            </div>
            <div class="news-summary">{_esc(summary)}</div>
        </div>'''

    return html


def _render_competitor(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-section">暂无竞对动态</div>'

    # Group by company
    groups: dict[str, list[dict]] = {}
    for item in items:
        extra = item.get("extra_data") or {}
        company = extra.get("company") or item.get("source") or "未知"
        if company not in groups:
            groups[company] = []
        groups[company].append(item)

    html = ""
    for company, comp_items in groups.items():
        items_html = ""
        for item in comp_items:
            extra = item.get("extra_data") or {}
            event_type = extra.get("event_type", "news")
            type_labels = {
                "product_update": "产品",
                "bidding_win": "中标",
                "partnership": "合作",
                "recruitment": "招聘",
                "award": "荣誉",
                "news": "动态",
            }
            type_label = type_labels.get(event_type, "动态")

            items_html += f'''<div class="comp-item">
                <span class="comp-type">{type_label}</span>
                <span>{_esc(item["title"])}</span>
            </div>'''

        html += f'''<div class="comp-group">
            <div class="comp-company">{_esc(company)}</div>
            {items_html}
        </div>'''

    return html


_AI_SUB_LABELS = {
    "llm": "大模型",
    "agent": "Agent",
    "aigc": "AIGC",
    "robotics": "机器人",
    "chip": "芯片",
    "general": "综合",
}


def _render_ai(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-section">暂无AI资讯</div>'

    html = ""
    for item in items:
        extra = item.get("extra_data") or {}
        sub_cat = extra.get("sub_category", "general")
        sub_label = _AI_SUB_LABELS.get(sub_cat, "综合")
        source = item.get("source") or ""
        summary = item.get("summary") or (item.get("content") or "")[:80]

        html += f'''<div class="ai-item">
            <div class="ai-title">{_esc(item["title"])}</div>
            <div class="ai-meta">
                <span class="ai-tag">{sub_label}</span>
                <span>{_esc(source)}</span>
            </div>
            <div class="ai-summary">{_esc(summary)}</div>
        </div>'''

    return html


# ---------------------------------------------------------------------------
# Full HTML assembly
# ---------------------------------------------------------------------------


def _render_express_html(
    target_date: date,
    sections_data: dict[str, list[dict]],
    total_count: int,
) -> str:
    """Render the complete daily express HTML."""

    date_str = target_date.strftime("%Y.%m.%d")
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_name = day_names[target_date.weekday()]

    # Stats bar
    stats_html = '<div class="stats-bar">'
    for cat_key, config in _CATEGORY_CONFIG.items():
        count = len(sections_data.get(cat_key, []))
        stats_html += f'''<div class="stat-cell">
            <div class="stat-icon">{config["icon"]}</div>
            <div class="stat-num" style="color:{config['color']}">{count}</div>
            <div class="stat-label">{config["label"]}</div>
        </div>'''
    stats_html += '</div>'

    # Sections
    renderers = {
        "bidding": _render_bidding,
        "news": _render_news,
        "competitor": _render_competitor,
        "ai": _render_ai,
    }

    sections_html = ""
    section_num = 1
    for cat_key, config in _CATEGORY_CONFIG.items():
        items = sections_data.get(cat_key, [])
        count = len(items)
        rendered = renderers[cat_key](items)

        sections_html += f'''<div class="section">
            <div class="section-head">
                <div class="section-icon" style="background:{config['color']}15">{config["icon"]}</div>
                <span class="section-title" style="color:{config['color']}">{config["label"]}</span>
                <span class="section-count">{count} 条</span>
            </div>
            {rendered}
        </div>'''
        section_num += 1

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日速递 · {date_str}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="express">
    <div class="masthead">
        <div class="masthead-badge">营销速递 · Daily Express</div>
        <div class="masthead-title">营销<span class="accent">情报</span>速递</div>
        <div class="masthead-date">{date_str} · {day_name} · 共 {total_count} 条情报</div>
    </div>
    {stats_html}
    <div class="content">
        {sections_html}
    </div>
    <div class="footer">
        <div class="footer-text">营销数据驾驶舱 · 自动生成</div>
        <div class="footer-line">内部资料 · 请勿外传</div>
    </div>
</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_daily_express(
    db: AsyncSession,
    target_date: date,
) -> DailyExpress:
    """Generate daily express for a given date."""

    logger.info("Generating daily express: %s", target_date.isoformat())

    # 1. Query crawler items for the date
    stmt = (
        select(CrawlerItem)
        .where(CrawlerItem.published_at == target_date)
        .order_by(CrawlerItem.relevance_score.desc().nullslast())
    )
    result = await db.execute(stmt)
    all_items = result.scalars().all()

    # If no items for exact date, try created_at date
    if not all_items:
        start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        stmt = (
            select(CrawlerItem)
            .where(CrawlerItem.created_at >= start)
            .where(CrawlerItem.created_at < end)
            .order_by(CrawlerItem.relevance_score.desc().nullslast())
        )
        result = await db.execute(stmt)
        all_items = result.scalars().all()

    # 2. Group by category
    sections_data: dict[str, list[dict]] = {}
    for cat_key, config in _CATEGORY_CONFIG.items():
        cat_items = [i for i in all_items if i.category == cat_key]
        top_items = cat_items[: config["max_items"]]
        sections_data[cat_key] = [_item_to_dict(i) for i in top_items]

    total_count = sum(len(v) for v in sections_data.values())

    # 3. Render HTML
    html = _render_express_html(target_date, sections_data, total_count)

    # 4. Build sections summary
    sections_summary = []
    for cat_key, config in _CATEGORY_CONFIG.items():
        count = len(sections_data.get(cat_key, []))
        if count > 0:
            sections_summary.append({
                "type": config["label"],
                "category": cat_key,
                "count": count,
            })

    # 5. Store
    now = datetime.now(timezone.utc)
    express = DailyExpress(
        express_date=target_date,
        title=f"每日速递 · {target_date.isoformat()}",
        sections=sections_summary,
        html_content=html,
        push_status="draft",
    )
    db.add(express)
    await db.flush()

    logger.info(
        "Daily express done: date=%s, total=%d",
        target_date.isoformat(), total_count,
    )
    return express


def _item_to_dict(item: CrawlerItem) -> dict[str, Any]:
    """Convert CrawlerItem to dict for rendering."""

    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "summary": item.summary,
        "source": item.source,
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": item.relevance_score,
        "extra_data": item.extra_data,
    }


__all__ = ["generate_daily_express"]
