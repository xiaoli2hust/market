from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BotAuditLog,
    BotChannelAdapter,
    BotChannelBinding,
    BotCompliancePolicy,
    BotInboxItem,
    BotToolCall,
    CrawlerItem,
)
from .bot_text import _normalize_text


def _fallback_answer(skill_results: list[dict[str, Any]], evidence_records: list[dict[str, Any]]) -> str:
    if not skill_results:
        return "我没有找到可调用的 Skill。请先在 Skill 管理中启用对应能力。"
    lines = ["我已按受控 Skill 完成本轮测试。"]
    for result in skill_results:
        output = result.get("output") or {}
        if result["skill_key"] == "dingtalk.broadcast":
            lines.append("钉钉群发动作已生成待确认草稿建议，测试台不会直接发送外部消息。")
            continue
        count = len(result.get("evidence_records") or output.get("items") or output.get("signals") or [])
        lines.append(f"- {result['skill_name']}：命中 {count} 条证据。")
    if evidence_records:
        lines.append("重点依据：")
        for item in evidence_records[:5]:
            lines.append(f"- {item.get('title', '未命名')}：{item.get('snippet') or item.get('source') or '已命中'}")
    else:
        lines.append("本轮没有命中可确认的证据，不能把结论说成确定事实。")
    return "\n".join(lines)


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def _extract_terms(text: str) -> list[str]:
    raw = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text)
    stop = {"帮我", "一下", "这个", "那个", "看看", "分析", "查询", "总结", "情况", "相关", "什么", "如何"}
    result = []
    for item in raw:
        value = item.strip()
        if value and value not in stop and value not in result:
            result.append(value)
    return result[:12]


def _period_days(text: str) -> int:
    if _has_any(text, ["年", "全年", "自然年", "26年", "2026"]):
        return 365
    if _has_any(text, ["周", "本周", "上周"]):
        return 14
    return 45 if _has_any(text, ["月", "本月", "上月"]) else 30


def _crawler_evidence(row: CrawlerItem) -> dict[str, Any]:
    return {
        "evidence_id": f"CRAWLER-{row.category}-{row.id}",
        "source_type": "crawler_item",
        "title": row.title,
        "source": row.source,
        "category": row.category,
        "source_url": row.source_url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "amount_wan": row.amount_wan,
        "buyer": row.buyer,
        "region": row.region,
        "score": row.relevance_score,
        "snippet": row.summary or _snippet(row.content or "", _extract_terms(row.title)),
        "record_id": row.id,
    }


def _market_directions(rows: list[CrawlerItem]) -> list[str]:
    if not rows:
        return ["未命中足够政策/市场证据，建议先补充采集或扩大关键词。"]
    text = " ".join(f"{row.title} {row.summary or ''}" for row in rows)
    directions = []
    for keyword, direction in (
        ("空间", "空间数据、地图和地址治理仍是高相关切入点。"),
        ("公安", "公安治理场景需要关注数据治理、智能指挥和安全合规。"),
        ("政数", "政数局相关信号适合跟进数据要素、城市治理和平台整合机会。"),
        ("电力", "电力场景可关注巡检、资产空间化和智能运维。"),
        ("运营商", "运营商方向可关注数据能力开放、云网融合和行业平台合作。"),
        ("AI", "AI Agent 方向适合与业务流程自动化、知识检索和数据分析结合。"),
    ):
        if keyword in text:
            directions.append(direction)
    return directions[:5] or ["当前信号分散，建议按行业和客户类型进一步聚类后再判断市场导向。"]


def _snippet(text: str | None, terms: list[str], limit: int = 180) -> str:
    clean = _normalize_text(text or "")
    if not clean:
        return ""
    pos = 0
    for term in terms:
        found = clean.find(term)
        if found >= 0:
            pos = max(0, found - 40)
            break
    return clean[pos: pos + limit]


def _tool_call(
    tool_name: str,
    status: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
) -> BotToolCall:
    now = datetime.now(timezone.utc)
    return BotToolCall(
        skill_run_id=0,
        tool_name=tool_name,
        status=status,
        input_payload=input_payload,
        output_payload=output_payload,
        started_at=now,
        finished_at=now,
        duration_ms=0,
    )


async def _adapter_for_channel(db: AsyncSession, channel_type: str) -> BotChannelAdapter | None:
    return (
        await db.execute(
            select(BotChannelAdapter)
            .where(BotChannelAdapter.channel_type == channel_type, BotChannelAdapter.status == "enabled")
            .order_by(BotChannelAdapter.id.asc())
        )
    ).scalars().first()


def _inbound_event_keys(
    binding: BotChannelBinding,
    sender_id: str | None,
    content: str,
    raw_payload: dict[str, Any],
    now: datetime,
) -> tuple[str, str]:
    external_id = str(raw_payload.get("event_id") or raw_payload.get("message_id") or raw_payload.get("msg_id") or "").strip()
    if external_id:
        event_id = external_id[:100]
        return f"{binding.channel_key}:{event_id}"[:160], event_id
    minute_bucket = now.strftime("%Y%m%d%H%M")
    digest = hashlib.sha256(f"{binding.channel_key}|{sender_id}|{content}|{minute_bucket}".encode("utf-8")).hexdigest()[:24]
    event_id = f"EV-{digest}"
    return f"{binding.channel_key}:{event_id}"[:160], event_id


async def _check_compliance(db: AsyncSession, content: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(BotCompliancePolicy).where(BotCompliancePolicy.status == "enabled"))
    ).scalars().all()
    issues: list[dict[str, Any]] = []
    for row in rows:
        rules = row.rules or {}
        for term in rules.get("blocked_terms", []) or []:
            clean_term = str(term).strip()
            if clean_term and clean_term in content:
                issues.append({"policy_key": row.policy_key, "name": row.name, "term": clean_term, "action": row.action})
    return issues


async def _upsert_inbox_item(
    db: AsyncSession,
    *,
    binding: BotChannelBinding,
    result: dict[str, Any],
    sender_name: str | None,
    content: str,
    compliance: list[dict[str, Any]],
) -> BotInboxItem:
    conversation = result.get("conversation") or {}
    conversation_id = str(conversation.get("conversation_id") or "")
    row = (
        await db.execute(select(BotInboxItem).where(BotInboxItem.conversation_id == conversation_id))
    ).scalar_one_or_none()
    title = content[:80] or conversation.get("title") or "群聊消息"
    priority = "P1" if compliance else "P2"
    tags = [item.get("policy_key") for item in compliance if item.get("policy_key")]
    now = datetime.now(timezone.utc)
    if not row:
        row = BotInboxItem(
            inbox_id=f"BI-{uuid.uuid4().hex[:12]}",
            conversation_id=conversation_id,
            channel_key=binding.channel_key,
            channel_name=binding.channel_name,
            profile_key=binding.bot_profile_key,
            title=title,
            sender_name=sender_name,
            status="open",
            priority=priority,
            tags=tags,
            last_message_at=now,
        )
        db.add(row)
    else:
        row.title = title
        row.sender_name = sender_name or row.sender_name
        row.priority = "P1" if priority == "P1" else row.priority
        row.tags = sorted(set((row.tags or []) + tags))
        row.last_message_at = now
        row.updated_at = now
    return row


def _audit(
    db: AsyncSession,
    *,
    event_type: str,
    user: dict[str, Any],
    profile_key: str | None = None,
    conversation_id: str | None = None,
    skill_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        BotAuditLog(
            event_type=event_type,
            profile_key=profile_key,
            conversation_id=conversation_id,
            skill_key=skill_key,
            actor_id=_user_id(user),
            actor_name=_user_name(user),
            payload=payload or {},
        )
    )


def _user_id(user: dict[str, Any]) -> int | None:
    value = user.get("id")
    return int(value) if isinstance(value, int) or str(value or "").isdigit() else None


def _user_name(user: dict[str, Any]) -> str:
    return str(user.get("display_name") or user.get("username") or user.get("sub") or "系统用户")


def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)[:12000]
