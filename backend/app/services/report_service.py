"""Report generation service: daily/weekly report with editorial-style HTML.

Pipeline:
1. Query activities for target date range
2. Call LLM for AI summary (fallback to data-only if LLM unavailable)
3. Render beautiful HTML report with statistics, color-coded activities
4. Generate access_token for leader viewing (30-day expiry)
5. Store in database

Design: Editorial business intelligence style
- Vermilion (#C53A2C) + warm paper (#F5EFE3) palette
- Mobile-first responsive layout
- Print-friendly
- Self-contained inline CSS (no external dependencies)
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Activity, ReportPage, Staff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Activity type color map
# ---------------------------------------------------------------------------

_TYPE_COLORS = {
    "client_visit": ("#2B5F8A", "Client Visit"),
    "opportunity_track": ("#C77A2E", "Opportunity"),
    "proposal_write": ("#3F8B8B", "Proposal"),
    "project_advance": ("#3F7A4A", "Project"),
    "channel_expand": ("#6A4C8A", "Channel"),
    "payment_follow": ("#C53A2C", "Payment"),
    "tech_exchange": ("#3B4A6B", "Tech Exchange"),
    "poc_test": ("#A8482A", "POC Test"),
    "bidding": ("#9C3D6B", "Bidding"),
    "contract_negotiate": ("#A37A1F", "Contract"),
    "client_maintain": ("#5F7A2E", "Maintenance"),
}

_DEFAULT_COLOR = ("#7A6F62", "Other")

# Chinese label map
_TYPE_LABELS = {
    "client_visit": "拜访客户",
    "opportunity_track": "商机跟进",
    "proposal_write": "方案撰写",
    "project_advance": "项目推进",
    "channel_expand": "渠道拓展",
    "payment_follow": "回款跟进",
    "tech_exchange": "技术交流",
    "poc_test": "POC测试",
    "bidding": "招投标",
    "contract_negotiate": "合同谈判",
    "client_maintain": "客户维护",
}


# ---------------------------------------------------------------------------
# HTML template — editorial style
# ---------------------------------------------------------------------------

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    color: #1a1714; background: #f5efe3; line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
.report { max-width: 680px; margin: 0 auto; background: #faf6ec; }

/* Masthead */
.masthead {
    background: #1a1714; color: #faf6ec; padding: 28px 24px 20px;
    position: relative; overflow: hidden;
}
.masthead::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 4px; background: #C53A2C;
}
.masthead-eyebrow {
    font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase;
    color: rgba(250,246,236,0.6); margin-bottom: 8px;
}
.masthead-title {
    font-size: 26px; font-weight: 800; line-height: 1.2; margin-bottom: 6px;
}
.masthead-title .accent { color: #C53A2C; }
.masthead-meta {
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-top: 12px; padding-top: 12px;
    border-top: 1px solid rgba(250,246,236,0.15);
}
.masthead-date { font-size: 14px; font-weight: 600; }
.masthead-issue { font-size: 11px; color: rgba(250,246,236,0.5); letter-spacing: 0.12em; }

/* Stats bar */
.stats-bar {
    display: flex; background: #1a1714; padding: 0;
}
.stat-cell {
    flex: 1; text-align: center; padding: 14px 8px;
    border-right: 1px solid rgba(250,246,236,0.1);
}
.stat-cell:last-child { border-right: none; }
.stat-num {
    font-size: 28px; font-weight: 800; color: #C53A2C;
    font-family: Georgia, 'Times New Roman', serif;
}
.stat-label {
    font-size: 10px; color: rgba(250,246,236,0.5);
    letter-spacing: 0.12em; text-transform: uppercase; margin-top: 2px;
}

/* Content sections */
.content { padding: 0 24px; }
.section {
    padding: 20px 0; border-bottom: 1px dashed rgba(26,23,20,0.15);
}
.section:last-child { border-bottom: none; }
.section-head {
    display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
}
.section-num {
    font-size: 11px; font-weight: 700; color: #C53A2C;
    font-family: Georgia, serif; letter-spacing: 0.06em;
}
.section-title {
    font-size: 16px; font-weight: 700; color: #1a1714;
}

/* AI Summary */
.summary-block {
    background: #fff; border-left: 4px solid #C53A2C;
    padding: 16px 18px; margin-bottom: 4px; border-radius: 0 4px 4px 0;
}
.summary-text {
    font-size: 14px; line-height: 1.9; color: #3b342d;
    white-space: pre-wrap;
}

/* Note */
.note-block {
    background: rgba(197,58,44,0.06); border: 1px dashed rgba(197,58,44,0.3);
    padding: 12px 16px; margin-top: 12px; border-radius: 4px;
    font-size: 13px; color: #3b342d; line-height: 1.7;
}
.note-label {
    font-size: 11px; font-weight: 700; color: #C53A2C;
    letter-spacing: 0.1em; margin-bottom: 4px;
}

/* Staff group */
.staff-group { margin-bottom: 18px; }
.staff-header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.staff-seal {
    width: 32px; height: 32px; background: #C53A2C; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 700; border-radius: 2px;
    font-family: Georgia, serif;
}
.staff-name { font-size: 15px; font-weight: 700; color: #1a1714; }
.staff-dept { font-size: 12px; color: #7a6f62; margin-left: 4px; }
.staff-count {
    font-size: 11px; color: #7a6f62; margin-left: auto;
    font-family: Georgia, serif;
}

/* Activity items */
.activity-list { list-style: none; }
.activity-item {
    display: flex; gap: 10px; padding: 8px 12px;
    margin-bottom: 4px; background: #fff; border-radius: 4px;
    border: 1px solid rgba(26,23,20,0.06);
    transition: box-shadow 0.15s;
}
.activity-item:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.activity-dot {
    width: 8px; height: 8px; border-radius: 50%;
    margin-top: 6px; flex-shrink: 0;
}
.activity-body { flex: 1; min-width: 0; }
.activity-type {
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    display: inline-block; margin-bottom: 2px;
}
.activity-target {
    font-size: 12px; color: #7a6f62; margin-left: 8px;
}
.activity-desc {
    font-size: 13px; color: #3b342d; line-height: 1.6; margin-top: 2px;
}
.activity-opp {
    display: inline-block; font-size: 11px; color: #A8482A;
    background: rgba(168,72,42,0.08); padding: 1px 8px;
    border-radius: 10px; margin-top: 4px;
}

/* Weekly extras */
.trend-chart {
    display: flex; align-items: flex-end; gap: 6px;
    height: 80px; padding: 8px 0;
}
.trend-bar-wrap {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; gap: 4px;
}
.trend-bar {
    width: 100%; max-width: 36px; background: #C53A2C;
    border-radius: 2px 2px 0 0; min-height: 4px;
    transition: height 0.3s;
}
.trend-label {
    font-size: 10px; color: #7a6f62;
    font-family: Georgia, serif;
}
.trend-count {
    font-size: 10px; color: #1a1714; font-weight: 700;
}

/* Ranking */
.rank-list { list-style: none; }
.rank-item {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; border-bottom: 1px dashed rgba(26,23,20,0.1);
}
.rank-item:last-child { border-bottom: none; }
.rank-num {
    font-size: 18px; font-weight: 800; color: #C53A2C;
    font-family: Georgia, serif; width: 28px; text-align: center;
}
.rank-num.top { color: #C53A2C; }
.rank-name { font-size: 14px; font-weight: 600; flex: 1; }
.rank-bar-wrap {
    width: 120px; height: 6px; background: rgba(26,23,20,0.08);
    border-radius: 3px; overflow: hidden;
}
.rank-bar {
    height: 100%; background: #C53A2C; border-radius: 3px;
}
.rank-count {
    font-size: 12px; color: #7a6f62;
    font-family: Georgia, serif; width: 40px; text-align: right;
}

/* Footer */
.footer {
    text-align: center; padding: 20px 24px;
    border-top: 1px solid rgba(26,23,20,0.1);
    background: #f5efe3;
}
.footer-text {
    font-size: 11px; color: #7a6f62; letter-spacing: 0.08em;
}
.footer-line {
    font-size: 10px; color: rgba(122,111,98,0.6); margin-top: 4px;
}

@media print {
    body { background: #fff; }
    .report { box-shadow: none; }
}
"""


# ---------------------------------------------------------------------------
# Data query
# ---------------------------------------------------------------------------


async def _query_activities(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> list[tuple[Activity, Staff]]:
    """Query activities with staff info for a date range."""

    stmt = (
        select(Activity, Staff)
        .join(Staff, Activity.staff_id == Staff.id)
        .where(Activity.report_date >= start_date)
        .where(Activity.report_date <= end_date)
        .order_by(Staff.name, Activity.report_date, Activity.activity_type)
    )
    result = await db.execute(stmt)
    return list(result.all())


def _group_by_staff(
    rows: list[tuple[Activity, Staff]],
) -> dict[str, list[dict[str, Any]]]:
    """Group activities by staff member."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for activity, staff in rows:
        key = staff.name
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "department": staff.department,
            "activity_type": activity.activity_type,
            "target": activity.target or "-",
            "opportunity": activity.opportunity or None,
            "opportunity_id": activity.opportunity_id or None,
            "description": activity.description or "",
            "report_date": activity.report_date.isoformat(),
        })
    return grouped


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _compute_stats(
    rows: list[tuple[Activity, Staff]],
    grouped: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Compute summary statistics."""

    total = len(rows)
    staff_count = len(grouped)
    opportunities = set()
    visit_count = 0
    type_counts: dict[str, int] = {}

    for activities in grouped.values():
        for a in activities:
            if a["opportunity"]:
                opportunities.add(a["opportunity"])
            if a["activity_type"] == "client_visit":
                visit_count += 1
            t = a["activity_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total": total,
        "staff_count": staff_count,
        "opportunity_count": len(opportunities),
        "visit_count": visit_count,
        "type_counts": type_counts,
    }


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------


async def _call_llm(system_prompt: str, user_content: str) -> str | None:
    """Call LLM API for summary. Returns None on failure."""

    if not settings.LLM_API_KEY:
        logger.info("LLM_API_KEY not configured, skipping AI summary")
        return None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("LLM call failed, falling back to data-only report")
        return None


_DAILY_SYSTEM_PROMPT = """\
You are a marketing team briefing writer. Summarize the provided activity data into a concise daily report.

Requirements:
1. Summarize each person's work for the day
2. Highlight key opportunity progress
3. Note 1-2 standout achievements
4. Style: professional internal briefing, concise
5. Output summary text only, no headers
"""

_WEEKLY_SYSTEM_PROMPT = """\
You are a marketing team briefing writer. Summarize the provided weekly activity data.

Requirements:
1. Overall stats (total activities, headcount, opportunities covered)
2. Key opportunity progress summary
3. Staff workload ranking
4. Suggested focus areas for next week
5. Style: professional internal briefing, concise
6. Output summary text only, no headers
"""


def _build_user_content(
    grouped: dict[str, list[dict[str, Any]]],
    extra: str = "",
) -> str:
    """Serialize grouped data for LLM input."""

    lines: list[str] = []
    if extra:
        lines.append(extra)
        lines.append("")

    for staff_name, activities in grouped.items():
        dept = activities[0]["department"] if activities else ""
        lines.append(f"## {staff_name} ({dept})")
        for a in activities:
            opp = f" | Opp: {a['opportunity']}" if a["opportunity"] else ""
            lines.append(
                f"- [{a['report_date']}] {a['activity_type']} | "
                f"Target: {a['target']}{opp} | {a['description']}"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_stats_bar(stats: dict[str, Any]) -> str:
    cells = [
        (stats["total"], "活动总数"),
        (stats["staff_count"], "活跃人数"),
        (stats["opportunity_count"], "覆盖商机"),
        (stats["visit_count"], "客户拜访"),
    ]
    html = '<div class="stats-bar">'
    for num, label in cells:
        html += f'''<div class="stat-cell">
            <div class="stat-num">{num}</div>
            <div class="stat-label">{label}</div>
        </div>'''
    html += '</div>'
    return html


def _render_summary_section(summary: str | None) -> str:
    if not summary:
        return ""
    return f'''<div class="section">
        <div class="section-head">
            <span class="section-num">I.</span>
            <span class="section-title">AI 摘要</span>
        </div>
        <div class="summary-block">
            <div class="summary-text">{_html_escape(summary)}</div>
        </div>
    </div>'''


def _render_note_section(note: str | None) -> str:
    if not note:
        return ""
    return f'''<div class="note-block">
        <div class="note-label">编者备注</div>
        {_html_escape(note)}
    </div>'''


def _render_activity_item(a: dict[str, Any]) -> str:
    type_color, _ = _TYPE_COLORS.get(a["activity_type"], _DEFAULT_COLOR)
    cn_label = _TYPE_LABELS.get(a["activity_type"], a["activity_type"])
    target = _html_escape(a["target"]) if a["target"] != "-" else ""
    desc = _html_escape(a["description"])
    opp_html = ""
    if a.get("opportunity"):
        opp_html = f'<div class="activity-opp">{_html_escape(a["opportunity"])}</div>'
    target_html = f'<span class="activity-target">{target}</span>' if target else ""

    return f'''<li class="activity-item">
        <div class="activity-dot" style="background:{type_color}"></div>
        <div class="activity-body">
            <span class="activity-type" style="color:{type_color}">{cn_label}</span>
            {target_html}
            <div class="activity-desc">{desc}</div>
            {opp_html}
        </div>
    </li>'''


def _render_staff_group(staff_name: str, activities: list[dict[str, Any]]) -> str:
    dept = activities[0]["department"] if activities else ""
    initial = staff_name[0].upper() if staff_name else "?"
    count = len(activities)
    items_html = "".join(_render_activity_item(a) for a in activities)

    return f'''<div class="staff-group">
        <div class="staff-header">
            <div class="staff-seal">{initial}</div>
            <span class="staff-name">{_html_escape(staff_name)}</span>
            <span class="staff-dept">{_html_escape(dept)}</span>
            <span class="staff-count">{count} 条</span>
        </div>
        <ul class="activity-list">{items_html}</ul>
    </div>'''


def _render_activities_section(grouped: dict[str, list[dict[str, Any]]], section_num: str = "II.") -> str:
    if not grouped:
        return f'''<div class="section">
            <div class="section-head">
                <span class="section-num">{section_num}</span>
                <span class="section-title">活动明细</span>
            </div>
            <p style="color:#7a6f62;font-size:14px;">暂无活动记录。</p>
        </div>'''

    staff_html = ""
    for staff_name, activities in sorted(grouped.items()):
        staff_html += _render_staff_group(staff_name, activities)

    return f'''<div class="section">
        <div class="section-head">
            <span class="section-num">{section_num}</span>
            <span class="section-title">活动明细</span>
        </div>
        {staff_html}
    </div>'''


def _render_trend_chart(grouped: dict[str, list[dict[str, Any]]], start: date, end: date) -> str:
    day_counts: dict[str, int] = {}
    for activities in grouped.values():
        for a in activities:
            d = a["report_date"]
            day_counts[d] = day_counts.get(d, 0) + 1

    max_count = max(day_counts.values()) if day_counts else 1
    bars_html = ""
    current = start
    while current <= end:
        d_str = current.isoformat()
        count = day_counts.get(d_str, 0)
        height_pct = int((count / max(max_count, 1)) * 60) if count > 0 else 0
        day_names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        label = day_names[current.weekday()]
        bars_html += f'''<div class="trend-bar-wrap">
            <div class="trend-count">{count if count else ""}</div>
            <div class="trend-bar" style="height:{max(height_pct, 4)}px;opacity:{0.4 + 0.6 * count / max(max_count, 1)}"></div>
            <div class="trend-label">{label}</div>
        </div>'''
        current += timedelta(days=1)

    return f'''<div class="section">
        <div class="section-head">
            <span class="section-num">II.</span>
            <span class="section-title">本周趋势</span>
        </div>
        <div class="trend-chart">{bars_html}</div>
    </div>'''


def _render_ranking(grouped: dict[str, list[dict[str, Any]]]) -> str:
    ranking = sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True)
    max_count = len(ranking[0][1]) if ranking else 1

    items_html = ""
    for i, (name, activities) in enumerate(ranking):
        count = len(activities)
        bar_pct = int(count / max(max_count, 1) * 100)
        rank_class = "top" if i < 3 else ""
        items_html += f'''<li class="rank-item">
            <span class="rank-num {rank_class}">{i + 1}</span>
            <span class="rank-name">{_html_escape(name)}</span>
            <div class="rank-bar-wrap"><div class="rank-bar" style="width:{bar_pct}%"></div></div>
            <span class="rank-count">{count}</span>
        </li>'''

    return f'''<div class="section">
        <div class="section-head">
            <span class="section-num">III.</span>
            <span class="section-title">人员排名</span>
        </div>
        <ul class="rank-list">{items_html}</ul>
    </div>'''


def _render_full_html(
    title: str,
    date_range: str,
    issue: str,
    stats: dict[str, Any],
    summary: str | None,
    note: str | None,
    sections: list[str],
) -> str:
    body = "".join(sections)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="report">
    <div class="masthead">
        <div class="masthead-eyebrow">营销数据驾驶舱 · Marketing Data Cockpit</div>
        <div class="masthead-title">{_html_escape(title)}</div>
        <div class="masthead-meta">
            <div class="masthead-date">{_html_escape(date_range)}</div>
            <div class="masthead-issue">{issue}</div>
        </div>
    </div>
    {_render_stats_bar(stats)}
    <div class="content">
        {_render_summary_section(summary)}
        {_render_note_section(note)}
        {body}
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


async def generate_daily_report(
    db: AsyncSession,
    target_date: date,
    note: str | None = None,
) -> ReportPage:
    """Generate a daily report page."""

    logger.info("Generating daily report: %s", target_date.isoformat())

    rows = await _query_activities(db, target_date, target_date)
    grouped = _group_by_staff(rows) if rows else {}
    stats = _compute_stats(rows, grouped)

    summary = None
    if grouped:
        user_content = _build_user_content(grouped)
        summary = await _call_llm(_DAILY_SYSTEM_PROMPT, user_content)

    day_of_year = target_date.timetuple().tm_yday
    issue = f"Vol.{target_date.year} / No.{day_of_year:03d}"
    title = "营销日报"
    date_range = target_date.strftime("%Y.%m.%d")

    activities_section = _render_activities_section(grouped, section_num="II.")
    sections = [activities_section]

    html = _render_full_html(
        title=title, date_range=date_range, issue=issue,
        stats=stats, summary=summary, note=note, sections=sections,
    )

    now = datetime.now(timezone.utc)
    report = ReportPage(
        report_type="daily",
        report_date=target_date,
        title=f"营销日报 · {target_date.isoformat()}",
        note=note,
        html_content=html,
        access_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(days=30),
        push_status="draft",
    )
    db.add(report)
    await db.flush()

    logger.info("Daily report done: date=%s, activities=%d", target_date.isoformat(), len(rows))
    return report


async def generate_weekly_report(
    db: AsyncSession,
    week_start: date,
    note: str | None = None,
) -> ReportPage:
    """Generate a weekly report page."""

    week_end = week_start + timedelta(days=6)
    logger.info("Generating weekly report: %s ~ %s", week_start, week_end)

    rows = await _query_activities(db, week_start, week_end)
    grouped = _group_by_staff(rows) if rows else {}
    stats = _compute_stats(rows, grouped)

    summary = None
    if grouped:
        extra = (
            f"Week stats: {stats['total']} activities, "
            f"{stats['staff_count']} staff, "
            f"{stats['opportunity_count']} opportunities."
        )
        user_content = _build_user_content(grouped, extra=extra)
        summary = await _call_llm(_WEEKLY_SYSTEM_PROMPT, user_content)

    day_of_year = week_start.timetuple().tm_yday
    issue = f"Vol.{week_start.year} / No.{day_of_year:03d}"
    title = "营销周报"
    date_range = f"{week_start.strftime('%Y.%m.%d')} ~ {week_end.strftime('%Y.%m.%d')}"

    sections = [
        _render_trend_chart(grouped, week_start, week_end),
        _render_ranking(grouped),
        _render_activities_section(grouped, section_num="IV."),
    ]

    html = _render_full_html(
        title=title, date_range=date_range, issue=issue,
        stats=stats, summary=summary, note=note, sections=sections,
    )

    now = datetime.now(timezone.utc)
    report = ReportPage(
        report_type="weekly",
        report_date=week_start,
        title=f"营销周报 · {week_start.isoformat()} ~ {week_end.isoformat()}",
        note=note,
        html_content=html,
        access_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(days=30),
        push_status="draft",
    )
    db.add(report)
    await db.flush()

    logger.info("Weekly report done: %s~%s, activities=%d", week_start, week_end, len(rows))
    return report


__all__ = ["generate_daily_report", "generate_weekly_report"]
