"""报告生成服务：日报/周报自动生成与渲染。

职责：
- 查询指定日期范围的活动数据，调用 LLM 生成结构化摘要；
- 将 AI 摘要与原始数据渲染为内联 CSS 的 HTML 报告；
- 生成带有效期的 access_token 用于领导查阅；
- LLM 不可用时自动降级为纯数据列表报告。

设计要点：
- 全异步，db session 由调用方注入；
- 异常绝不冒泡，LLM 失败降级到原始数据报告；
- HTML 内联 CSS，手机友好，不依赖外部资源。
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..models import Activity, ReportPage, Staff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------

_REPORT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #333; background: #f5f5f5; line-height: 1.6; padding: 16px;
  }}
  .container {{ max-width: 680px; margin: 0 auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .header {{ background: #C53030; color: #fff; padding: 24px 20px; }}
  .header h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }}
  .header .date {{ font-size: 14px; opacity: .9; }}
  .section {{ padding: 20px; border-bottom: 1px solid #eee; }}
  .section:last-child {{ border-bottom: none; }}
  .section h2 {{ font-size: 16px; color: #C53030; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid #C53030; display: inline-block; }}
  .section h3 {{ font-size: 14px; color: #333; margin: 10px 0 6px; font-weight: 600; }}
  .summary {{ font-size: 14px; line-height: 1.8; white-space: pre-wrap; }}
  .activity-list {{ list-style: none; padding: 0; }}
  .activity-list li {{
    padding: 8px 12px; margin-bottom: 6px; background: #fafafa;
    border-left: 3px solid #C53030; border-radius: 0 4px 4px 0; font-size: 13px;
  }}
  .activity-list li .label {{ color: #888; font-size: 12px; }}
  .activity-list li .value {{ color: #333; }}
  .staff-group {{ margin-bottom: 14px; }}
  .staff-name {{ font-weight: 600; color: #C53030; font-size: 14px; margin-bottom: 4px; }}
  .footer {{ text-align: center; padding: 16px; font-size: 12px; color: #999; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{title}</h1>
    <div class="date">{date_range}</div>
  </div>
  {body_sections}
  <div class="footer">由营销智能管理平台自动生成</div>
</div>
</body>
</html>
"""

_SECTION_SUMMARY = """\
<div class="section">
  <h2>AI 摘要</h2>
  <div class="summary">{summary_text}</div>
</div>
"""

_SECTION_ACTIVITIES = """\
<div class="section">
  <h2>活动明细</h2>
  {staff_groups}
</div>
"""

_STAFF_GROUP = """\
<div class="staff-group">
  <div class="staff-name">{staff_name}（{department}）</div>
  <ul class="activity-list">
    {activity_items}
  </ul>
</div>
"""

_ACTIVITY_ITEM = """\
<li>
  <span class="label">类型：</span><span class="value">{activity_type}</span>
  &nbsp;|&nbsp;
  <span class="label">对象：</span><span class="value">{target}</span>
  &nbsp;|&nbsp;
  <span class="label">商机：</span><span class="value">{opportunity}</span>
  <br><span class="value">{description}</span>
</li>
"""


# ---------------------------------------------------------------------------
# 数据查询
# ---------------------------------------------------------------------------

async def _query_activities(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> list[tuple[Activity, Staff]]:
    """查询日期范围内所有活动（含人员信息）。"""

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
    """按人员分组活动数据，返回 {staff_name: [activity_dict, ...]}。"""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for activity, staff in rows:
        key = staff.name
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(
            {
                "department": staff.department,
                "activity_type": activity.activity_type,
                "target": activity.target or "-",
                "opportunity": activity.opportunity or "-",
                "description": activity.description or "",
                "report_date": activity.report_date.isoformat(),
            }
        )
    return grouped


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

async def _call_llm(system_prompt: str, user_content: str) -> str | None:
    """调用 DeepSeek API 生成摘要文本。失败返回 None。"""

    if not settings.LLM_API_KEY:
        logger.info("LLM_API_KEY 未配置，跳过 AI 摘要生成")
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
        logger.exception("LLM 调用失败，将降级为纯数据报告")
        return None


# ---------------------------------------------------------------------------
# 摘要 Prompt
# ---------------------------------------------------------------------------

_DAILY_SYSTEM_PROMPT = """\
你是一个营销团队内部简报撰写助手。请根据提供的活动数据，撰写一份简洁专业的日报摘要。

要求：
1. 按人员维度汇总每人当天做了什么
2. 按商机维度汇总各商机最新进展
3. 给出当天亮点（1-2条）
4. 风格简洁专业，像内部简报，不要啰嗦
5. 直接输出摘要文本，不要加标题
"""

_WEEKLY_SYSTEM_PROMPT = """\
你是一个营销团队内部简报撰写助手。请根据提供的本周活动数据，撰写一份简洁专业的周报摘要。

要求：
1. 本周整体活动量统计（总条数、人数、覆盖商机数）
2. 重点商机进展汇总
3. 各人员工作量排名
4. 下周建议关注点
5. 风格简洁专业，像内部简报，不要啰嗦
6. 直接输出摘要文本，不要加标题
"""


def _build_user_content(
    grouped: dict[str, list[dict[str, Any]]],
    extra_context: str = "",
) -> str:
    """把分组数据序列化为文本，供 LLM 输入。"""

    lines: list[str] = []
    if extra_context:
        lines.append(extra_context)
        lines.append("")

    for staff_name, activities in grouped.items():
        dept = activities[0]["department"] if activities else ""
        lines.append(f"## {staff_name}（{dept}）")
        for a in activities:
            lines.append(
                f"- [{a['report_date']}] {a['activity_type']} | "
                f"对象: {a['target']} | 商机: {a['opportunity']} | "
                f"{a['description']}"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML 渲染
# ---------------------------------------------------------------------------

def _render_activities_html(grouped: dict[str, list[dict[str, Any]]]) -> str:
    """把分组数据渲染为活动明细 HTML 片段。"""

    staff_groups_html = ""
    for staff_name, activities in grouped.items():
        dept = activities[0]["department"] if activities else ""
        items_html = ""
        for a in activities:
            items_html += _ACTIVITY_ITEM.format(
                activity_type=a["activity_type"],
                target=a["target"],
                opportunity=a["opportunity"],
                description=a["description"],
            )
        staff_groups_html += _STAFF_GROUP.format(
            staff_name=staff_name,
            department=dept,
            activity_items=items_html,
        )

    return _SECTION_ACTIVITIES.format(staff_groups=staff_groups_html)


def _render_report_html(
    title: str,
    date_range: str,
    summary: str | None,
    grouped: dict[str, list[dict[str, Any]]],
) -> str:
    """组装完整报告 HTML。"""

    body = ""
    if summary:
        body += _SECTION_SUMMARY.format(summary_text=summary)
    body += _render_activities_html(grouped)

    return _REPORT_HTML_TEMPLATE.format(
        title=title,
        date_range=date_range,
        body_sections=body,
    )


def _fallback_summary(grouped: dict[str, list[dict[str, Any]]]) -> str:
    """降级模式：用原始数据生成简单文本摘要。"""

    lines: list[str] = []
    for staff_name, activities in grouped.items():
        lines.append(f"【{staff_name}】")
        for a in activities:
            lines.append(f"  - {a['activity_type']}: {a['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

async def generate_daily_report(
    db: AsyncSession,
    target_date: date,
) -> ReportPage:
    """生成日报报告页面。

    流程：
    1. 查询当天活动 → 2. 调用 LLM 生成摘要 → 3. 渲染 HTML → 4. 写入数据库
    """

    logger.info("开始生成日报: %s", target_date.isoformat())

    # 1. 查询活动数据
    rows = await _query_activities(db, target_date, target_date)
    if not rows:
        logger.warning("当日无活动数据: %s", target_date.isoformat())
        # 仍然生成报告，只是无活动
        grouped: dict[str, list[dict[str, Any]]] = {}
    else:
        grouped = _group_by_staff(rows)

    # 2. 调用 LLM 生成摘要
    user_content = _build_user_content(grouped)
    summary: str | None = None
    if grouped:
        summary = await _call_llm(_DAILY_SYSTEM_PROMPT, user_content)
        if summary is None:
            # 降级：用原始数据生成文本摘要
            summary = _fallback_summary(grouped)
            logger.info("日报使用降级摘要: %s", target_date.isoformat())

    # 3. 渲染 HTML
    title = f"营销日报 · {target_date.isoformat()}"
    date_range = target_date.isoformat()
    html_content = _render_report_html(title, date_range, summary, grouped)

    # 4. 创建 ReportPage 记录
    now = datetime.now(timezone.utc)
    report = ReportPage(
        report_type="daily",
        report_date=target_date,
        title=title,
        note=None,
        html_content=html_content,
        access_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(days=30),
        push_status="draft",
    )
    db.add(report)
    await db.flush()

    logger.info(
        "日报生成完成: date=%s, token=%s, activities=%d",
        target_date.isoformat(),
        report.access_token,
        len(rows),
    )
    return report


async def generate_weekly_report(
    db: AsyncSession,
    week_start: date,
) -> ReportPage:
    """生成周报报告页面。

    流程：
    1. 查询 week_start ~ week_start+6 的活动 → 2. 调用 LLM 生成摘要 →
    3. 渲染 HTML → 4. 写入数据库
    """

    week_end = week_start + timedelta(days=6)
    logger.info(
        "开始生成周报: %s ~ %s", week_start.isoformat(), week_end.isoformat()
    )

    # 1. 查询活动数据
    rows = await _query_activities(db, week_start, week_end)
    if not rows:
        logger.warning("本周无活动数据: %s ~ %s", week_start.isoformat(), week_end.isoformat())
        grouped: dict[str, list[dict[str, Any]]] = {}
    else:
        grouped = _group_by_staff(rows)

    # 2. 构建统计上下文 + 调用 LLM
    total_activities = len(rows)
    total_staff = len(grouped)
    unique_opportunities: set[str] = set()
    for activities in grouped.values():
        for a in activities:
            if a["opportunity"] != "-":
                unique_opportunities.add(a["opportunity"])

    extra_context = (
        f"本周统计：共 {total_activities} 条活动，"
        f"{total_staff} 人参与，覆盖 {len(unique_opportunities)} 个商机。"
    )

    user_content = _build_user_content(grouped, extra_context=extra_context)
    summary: str | None = None
    if grouped:
        summary = await _call_llm(_WEEKLY_SYSTEM_PROMPT, user_content)
        if summary is None:
            summary = _fallback_summary(grouped)
            logger.info("周报使用降级摘要: %s", week_start.isoformat())

    # 3. 渲染 HTML
    title = f"营销周报 · {week_start.isoformat()} ~ {week_end.isoformat()}"
    date_range = f"{week_start.isoformat()} ~ {week_end.isoformat()}"
    html_content = _render_report_html(title, date_range, summary, grouped)

    # 4. 创建 ReportPage 记录
    now = datetime.now(timezone.utc)
    report = ReportPage(
        report_type="weekly",
        report_date=week_start,
        title=title,
        note=None,
        html_content=html_content,
        access_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(days=30),
        push_status="draft",
    )
    db.add(report)
    await db.flush()

    logger.info(
        "周报生成完成: week=%s, token=%s, activities=%d",
        week_start.isoformat(),
        report.access_token,
        len(rows),
    )
    return report


__all__ = [
    "generate_daily_report",
    "generate_weekly_report",
]
