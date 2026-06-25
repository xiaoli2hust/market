"""G端标讯线索确认路由。"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import CrawlerItem, OpportunityLead


router = APIRouter(prefix="/opportunity-leads", tags=["opportunity-leads"])

Decision = Literal["HIGH_PRIORITY", "MEDIUM", "LOW", "IGNORE"]
LeadStatus = Literal["new", "reviewing", "converted", "ignored"]


class DiscoverRequest(BaseModel):
    pages_per_source: int = Field(default=4, ge=1, le=10)
    persist: bool = True
    use_fallback: bool = True


class StatusUpdateRequest(BaseModel):
    status: LeadStatus


@router.get("/")
async def list_opportunity_leads(
    decision: str | None = Query(None, description="HIGH_PRIORITY/MEDIUM/LOW/IGNORE"),
    status: str | None = Query(None, description="new/reviewing/converted/ignored"),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("opportunities:view")),
) -> dict[str, Any]:
    conditions = []
    if decision:
        conditions.append(OpportunityLead.decision == decision)
    if status:
        conditions.append(OpportunityLead.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(
            or_(
                OpportunityLead.project_name.ilike(pattern),
                OpportunityLead.buyer.ilike(pattern),
                OpportunityLead.summary.ilike(pattern),
            )
        )

    count_stmt = select(func.count(OpportunityLead.id))
    list_stmt = select(OpportunityLead).where(OpportunityLead.source == "bidding")
    count_stmt = count_stmt.where(OpportunityLead.source == "bidding")
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = (await db.execute(count_stmt)).scalar_one() or 0
    rows = (
        await db.execute(
            list_stmt.order_by(
                OpportunityLead.score.desc(),
                OpportunityLead.budget.desc(),
                OpportunityLead.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [_lead_to_dict(row) for row in rows],
    }


@router.get("/stats")
async def opportunity_lead_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("opportunities:view")),
) -> dict[str, Any]:
    return await _build_stats(db)


@router.post("/discover")
async def discover_leads(
    payload: DiscoverRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("opportunities:manage")),
) -> dict[str, Any]:
    items = await _discover_from_bidding_items(db, limit=max(30, payload.pages_per_source * 30))

    saved = 0
    updated = 0
    leads: list[OpportunityLead] = []
    if payload.persist:
        for item in items:
            existing = (
                await db.execute(select(OpportunityLead).where(OpportunityLead.url == item["url"]))
            ).scalar_one_or_none()
            if existing:
                _apply_discovered_item(existing, item)
                updated += 1
                leads.append(existing)
            else:
                lead = OpportunityLead()
                _apply_discovered_item(lead, item)
                db.add(lead)
                saved += 1
                leads.append(lead)
        await db.flush()
        for lead in leads[:30]:
            await db.refresh(lead)
    else:
        leads = [_item_to_virtual_lead(item) for item in items]

    decision_counts = {key: 0 for key in ["HIGH_PRIORITY", "MEDIUM", "LOW", "IGNORE"]}
    for item in items:
        decision_counts[item.get("decision", "IGNORE")] = decision_counts.get(item.get("decision", "IGNORE"), 0) + 1

    stats = await _build_stats(db) if payload.persist else {}
    return {
        "total": len(items),
        "saved": saved,
        "updated": updated,
        "decision_counts": decision_counts,
        "items": [_lead_to_dict(lead) for lead in leads[:30]],
        "stats": stats,
    }


@router.put("/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    payload: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("opportunities:manage")),
) -> dict[str, Any]:
    lead = (
        await db.execute(select(OpportunityLead).where(OpportunityLead.id == lead_id))
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    lead.status = payload.status
    await db.flush()
    await db.refresh(lead)
    return _lead_to_dict(lead)


async def _build_stats(db: AsyncSession) -> dict[str, Any]:
    base_condition = OpportunityLead.source == "bidding"
    total = (await db.execute(select(func.count(OpportunityLead.id)).where(base_condition))).scalar_one() or 0
    actionable = (
        await db.execute(
            select(func.count(OpportunityLead.id)).where(base_condition, OpportunityLead.decision != "IGNORE")
        )
    ).scalar_one() or 0
    budget_total = (
        await db.execute(select(func.coalesce(func.sum(OpportunityLead.budget), 0)).where(base_condition))
    ).scalar_one() or 0
    avg_score = (
        await db.execute(select(func.coalesce(func.avg(OpportunityLead.score), 0)).where(base_condition))
    ).scalar_one() or 0
    latest = (await db.execute(select(func.max(OpportunityLead.created_at)).where(base_condition))).scalar_one_or_none()

    decision_rows = (
        await db.execute(
            select(OpportunityLead.decision, func.count(OpportunityLead.id))
            .where(base_condition)
            .group_by(OpportunityLead.decision)
        )
    ).all()
    status_rows = (
        await db.execute(
            select(OpportunityLead.status, func.count(OpportunityLead.id))
            .where(base_condition)
            .group_by(OpportunityLead.status)
        )
    ).all()

    return {
        "total": int(total),
        "actionable_count": int(actionable),
        "budget_total": float(budget_total or 0),
        "avg_score": float(avg_score or 0),
        "latest_created_at": latest.isoformat() if latest else None,
        "by_decision": {row[0]: int(row[1]) for row in decision_rows},
        "by_status": {row[0]: int(row[1]) for row in status_rows},
    }


def _apply_discovered_item(lead: OpportunityLead, item: dict[str, Any]) -> None:
    lead.project_name = item["project_name"][:500]
    lead.buyer = (item.get("buyer") or "")[:200] or None
    lead.budget = float(item.get("budget") or 0)
    lead.score = int(item.get("score") or 0)
    lead.decision = item.get("decision") or "IGNORE"
    lead.summary = item.get("summary")
    lead.why_it_matters = item.get("why_it_matters") or []
    lead.risks = item.get("risks") or []
    lead.recommended_action = item.get("recommended_action") or []
    lead.url = item["url"][:500]
    lead.source = "bidding"
    lead.source_category = (item.get("source_category") or "")[:100] or None
    lead.procurement_method = (item.get("procurement_method") or "")[:80] or None
    lead.publish_date = _parse_publish_date(item.get("publish_date"))
    lead.raw_record = {
        "raw_record": item.get("raw_record") or {},
        "scoring_level": item.get("scoring_level"),
        "scoring_reason": item.get("scoring_reason") or [],
    }


def _item_to_virtual_lead(item: dict[str, Any]) -> OpportunityLead:
    lead = OpportunityLead(id=0)
    _apply_discovered_item(lead, item)
    now = datetime.utcnow()
    lead.created_at = now
    lead.updated_at = now
    lead.status = "new"
    return lead


def _lead_to_dict(lead: OpportunityLead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "project_name": lead.project_name,
        "buyer": lead.buyer,
        "budget": float(lead.budget or 0),
        "score": int(lead.score or 0),
        "decision": lead.decision,
        "summary": lead.summary,
        "why_it_matters": lead.why_it_matters or [],
        "risks": lead.risks or [],
        "recommended_action": lead.recommended_action or [],
        "url": lead.url,
        "source": lead.source,
        "source_category": lead.source_category,
        "procurement_method": lead.procurement_method,
        "publish_date": lead.publish_date.isoformat() if lead.publish_date else None,
        "status": lead.status,
        "raw_record": lead.raw_record or {},
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


async def _discover_from_bidding_items(db: AsyncSession, limit: int = 120) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(CrawlerItem)
            .where(CrawlerItem.category == "bidding")
            .where(CrawlerItem.relevance_score >= 30)
            .order_by(CrawlerItem.relevance_score.desc(), CrawlerItem.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = _bidding_item_to_lead(row)
        if item:
            items.append(item)
    items.sort(key=lambda item: (item["score"], item["budget"]), reverse=True)
    return items


def _bidding_item_to_lead(row: CrawlerItem) -> dict[str, Any] | None:
    extra = row.extra_data or {}
    profile = extra.get("agent_profile") or {}
    url = row.source_url or f"crawler-item:{row.id}"
    score = int(row.relevance_score or 0)
    if score < 30:
        return None

    buyer = str(extra.get("buyer") or "").strip()
    budget = _bidding_budget_rmb(row)
    topics = profile.get("topics") or []
    customer_types = profile.get("customer_types") or []
    decision = _decision_from_score(score, budget, customer_types)
    title = row.title or ""

    topic_text = "、".join(topics[:3]) or "未识别主题"
    customer_text = "、".join(customer_types[:2]) or "待确认客户类型"
    notice_type = _notice_type(extra)
    summary = _lead_summary(row, buyer, notice_type) or f"{buyer or '采购单位'}发布{title}，主题：{topic_text}。"

    why = [
        f"命中{topic_text}，与现有方案能力存在关联。",
        f"客户类型判断为{customer_text}，适合销售进一步核实场景。",
    ]
    risks = [
        "Agent 只做相关性研判，仍需人工确认预算、截止时间和采购边界。",
    ]
    if not budget:
        risks.append("预算金额未结构化识别，需查看原文补充。")
    if decision == "IGNORE":
        risks.append("相关性不足，建议仅归档观察。")

    recommended = [
        "人工确认是否与当前产品能力匹配。",
        "确认采购阶段、截止日期、联系人和代理机构。",
    ]
    if decision in {"HIGH_PRIORITY", "MEDIUM"}:
        recommended.insert(0, "优先分配销售或售前做 24 小时内核实。")

    return {
        "project_name": title,
        "buyer": buyer,
        "budget": budget,
        "score": score,
        "decision": decision,
        "summary": summary,
        "why_it_matters": why,
        "risks": risks,
        "recommended_action": recommended,
        "url": url,
        "publish_date": row.published_at.isoformat() if row.published_at else None,
        "source": "bidding",
        "source_category": notice_type,
        "procurement_method": notice_type,
        "raw_record": {
            "crawler_item_id": row.id,
            "topics": topics,
            "customer_types": customer_types,
            "agent_profile": profile,
            "source": "标讯数据",
        },
    }


def _decision_from_score(score: int, budget: float, customer_types: list[str]) -> str:
    adjusted = score
    if budget >= 10000000:
        adjusted += 10
    if any(customer in customer_types for customer in ["公安客户", "政数客户", "自然资源客户"]):
        adjusted += 10
    if adjusted >= 80:
        return "HIGH_PRIORITY"
    if adjusted >= 60:
        return "MEDIUM"
    if adjusted >= 40:
        return "LOW"
    return "IGNORE"


def _lead_summary(row: CrawlerItem, buyer: str, notice_type: str) -> str | None:
    extra = row.extra_data or {}
    parts = []
    winner = str(extra.get("winner") or "").strip()
    budget = _bidding_budget_rmb(row)
    if buyer:
        parts.append(f"采购人: {buyer}")
    if winner:
        parts.append(f"中标: {winner}")
    if budget:
        parts.append(f"金额: {_format_rmb_budget(budget)}")
    if notice_type:
        parts.append(f"类型: {notice_type}")
    return " | ".join(parts) if parts else row.summary


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


def _parse_publish_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})", text)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _amount_to_rmb(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    if "亿" in text:
        return amount * 100000000
    if "万元" in text or "万" in text:
        return amount * 10000
    return amount


def _bidding_budget_rmb(row: CrawlerItem) -> float:
    extra = row.extra_data or {}
    for key in ("amount_wan", "bid_amount"):
        value = extra.get(key)
        amount = _amount_to_rmb(value)
        if amount > 0:
            if key in {"amount_wan", "bid_amount"} and "万" not in str(value) and "元" not in str(value) and "亿" not in str(value):
                return float(value) * 10000
            return amount
    return _parse_labeled_amount_rmb(" ".join([row.summary or "", row.content or "", row.title or ""]))


def _parse_labeled_amount_rmb(text: str) -> float:
    cleaned = re.sub(r"\s+", "", str(text or "").replace(",", ""))
    if not cleaned:
        return 0.0
    patterns = [
        r"(?:预算金额|预算价|项目预算|采购预算|最高限价|控制价|招标控制价|中标金额|成交金额|中标价|成交价|报价金额|合同金额|合同估算价|估算总投资)[^0-9¥￥]{0,20}[¥￥]?([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)?",
        r"(?:预算金额|预算|估算总投资|合同估算价)[（(](亿元|亿|万元|万|元)[）)][^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, cleaned)
        if not match:
            continue
        if index == 1:
            unit, amount = match.groups()
            return _amount_to_rmb(f"{amount}{unit}")
        amount, unit = match.groups()
        if unit:
            return _amount_to_rmb(f"{amount}{unit}")
        # 金额标签明确但单位缺失时，政府采购默认数字常为元，保守按元处理。
        return float(amount)
    return 0.0


def _format_rmb_budget(value: float) -> str:
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿元"
    return f"{value / 10000:.1f}万元"
