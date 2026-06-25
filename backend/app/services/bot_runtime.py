"""Agent runtime for the Bot Center.

The runtime keeps the product agent-native without hiding business logic in a
prompt: every answer is backed by selected skills, controlled data tools,
skill-run records and evidence snippets.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any, Callable

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Activity,
    BotAuditLog,
    BotChannelBinding,
    BotConversation,
    BotKnowledgeChunk,
    BotKnowledgeFile,
    BotMessage,
    BotProfile,
    BotSkill,
    BotSkillRun,
    BotToolCall,
    CrawlerItem,
    DepartmentWeeklyReport,
    DingtalkConfig,
    OpportunityLead,
)
from ..permissions import has_permission
from ..secret_store import decrypt_secret
from .llm_service import create_runtime_llm_service, get_runtime_llm_config


BOT_PROFILES: list[dict[str, Any]] = [
    {
        "profile_key": "market_intelligence_agent",
        "name": "市场洞察机器人",
        "default_role": "市场负责人",
        "description": "负责标讯、政策、市场线索、竞对和行业知识的检索与分析。",
        "allowed_skills": [
            "knowledge.search",
            "market.bidding_search",
            "market.bidding_analysis",
            "market.policy_market_tracking",
            "dingtalk.broadcast",
        ],
    },
    {
        "profile_key": "daily_report_agent",
        "name": "日报周报机器人",
        "default_role": "部门管理者",
        "description": "负责日报活动、部门周报归档和阶段性总结。",
        "allowed_skills": [
            "knowledge.search",
            "report.weekly_archive_summary",
            "dingtalk.broadcast",
        ],
    },
    {
        "profile_key": "opportunity_followup_agent",
        "name": "商机跟进机器人",
        "default_role": "销售管理者",
        "description": "围绕销售已维护的商机、签单预测和回款预测做进度跟进。",
        "allowed_skills": [
            "knowledge.search",
            "opportunity.followup_status",
            "dingtalk.broadcast",
        ],
    },
    {
        "profile_key": "management_assistant_agent",
        "name": "管理助手",
        "default_role": "经营管理者",
        "description": "面向管理者做跨模块问答、证据追踪和动作建议。",
        "allowed_skills": [
            "knowledge.search",
            "market.bidding_search",
            "market.bidding_analysis",
            "market.policy_market_tracking",
            "report.weekly_archive_summary",
            "opportunity.followup_status",
            "dingtalk.broadcast",
        ],
    },
]


BOT_SKILLS: list[dict[str, Any]] = [
    {
        "skill_key": "knowledge.search",
        "name": "知识检索",
        "category": "knowledge",
        "required_permission": "bot:view",
        "description": "从知识空间文件和部门周报文本中检索证据片段。",
        "trigger_scenarios": ["问制度、方案、空间数据、产品材料、历史周报、资料依据"],
        "input_contract": {"query": "用户问题", "category": "可选知识分类", "limit": "返回条数"},
        "output_contract": {"items": "命中的知识片段", "evidence_records": "可追溯证据"},
        "evidence_rules": {"required": True, "fields": ["title", "source", "snippet"]},
    },
    {
        "skill_key": "market.bidding_search",
        "name": "标讯检索",
        "category": "market",
        "required_permission": "intelligence:view",
        "description": "按关键词、时间、金额和地区检索已采集标讯。",
        "trigger_scenarios": ["查标讯、招投标、采购、预算金额、项目机会"],
        "input_contract": {"query": "检索关键词", "limit": "返回条数"},
        "output_contract": {"items": "标讯列表", "evidence_records": "标讯证据"},
        "evidence_rules": {"required": True, "fields": ["title", "source_url", "amount_wan", "published_at"]},
    },
    {
        "skill_key": "market.bidding_analysis",
        "name": "标讯分析",
        "category": "market",
        "required_permission": "intelligence:view",
        "description": "按周/月/年统计标讯数量、金额、地区、关键词和重点机会。",
        "trigger_scenarios": ["分析标讯趋势、行业分布、关键词触发、金额分布、重点标讯"],
        "input_contract": {"period": "week/month/year", "query": "可选关键词"},
        "output_contract": {"summary": "统计摘要", "distribution": "分布", "top_items": "重点标讯"},
        "evidence_rules": {"required": True, "fields": ["top_items", "range"]},
    },
    {
        "skill_key": "market.policy_market_tracking",
        "name": "政策与市场跟踪",
        "category": "market",
        "required_permission": "intelligence:view",
        "description": "跟踪政策法规和市场线索，并输出市场导向。",
        "trigger_scenarios": ["政策、政数、大数据、电力、运营商、空间数据、市场动态"],
        "input_contract": {"query": "关注主题", "period": "时间范围"},
        "output_contract": {"signals": "政策/市场信号", "directions": "市场导向"},
        "evidence_rules": {"required": True, "fields": ["source", "published_at", "summary"]},
    },
    {
        "skill_key": "report.weekly_archive_summary",
        "name": "周报归档总结",
        "category": "report",
        "required_permission": "reports:view",
        "description": "读取部门周报归档，回答某周发生了什么。",
        "trigger_scenarios": ["周报、部门总结、本周发生了什么、历史记录"],
        "input_contract": {"query": "问题", "department": "可选部门"},
        "output_contract": {"reports": "周报记录", "highlights": "摘要"},
        "evidence_rules": {"required": True, "fields": ["department", "week_start", "title"]},
    },
    {
        "skill_key": "opportunity.followup_status",
        "name": "商机跟进",
        "category": "opportunity",
        "required_permission": "opportunities:view",
        "description": "查询已识别/已确认商机状态，辅助销售进度跟进。",
        "trigger_scenarios": ["商机、签单、回款、销售跟进、预测进展"],
        "input_contract": {"query": "客户/项目/销售问题"},
        "output_contract": {"leads": "商机列表", "activities": "相关活动"},
        "evidence_rules": {"required": True, "fields": ["project_name", "buyer", "status"]},
    },
    {
        "skill_key": "dingtalk.broadcast",
        "name": "钉钉群发",
        "category": "action",
        "required_permission": "bot:broadcast",
        "description": "把确认后的消息推送到钉钉群；测试对话中只生成待确认草稿。",
        "trigger_scenarios": ["群发、通知大家、发到钉钉、提醒所有人"],
        "input_contract": {"title": "消息标题", "content": "消息正文", "at_all": "是否提醒所有人"},
        "output_contract": {"requires_confirmation": "是否需要确认", "suggested_payload": "建议消息"},
        "evidence_rules": {"required": False, "action_confirmation": True},
    },
]

_DEFAULTS_LOCK = asyncio.Lock()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag.lower() in {"script", "style", "iframe", "object", "embed"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "iframe", "object", "embed"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", unescape(data)).strip()
        if text:
            self.parts.append(text)


async def ensure_bot_runtime_defaults(db: AsyncSession) -> None:
    """Seed default bot profiles, skills and the default DingTalk channel binding."""

    async with _DEFAULTS_LOCK:
        try:
            await _ensure_bot_runtime_defaults_locked(db)
        except IntegrityError:
            await db.rollback()
            await _ensure_bot_runtime_defaults_locked(db)


async def _ensure_bot_runtime_defaults_locked(db: AsyncSession) -> None:
    """Write default records after the caller has acquired the init lock."""

    for item in BOT_SKILLS:
        row = (
            await db.execute(select(BotSkill).where(BotSkill.skill_key == item["skill_key"]))
        ).scalar_one_or_none()
        if row:
            row.name = item["name"]
            row.category = item["category"]
            row.description = item["description"]
            row.trigger_scenarios = item["trigger_scenarios"]
            row.input_contract = item["input_contract"]
            row.output_contract = item["output_contract"]
            row.evidence_rules = item["evidence_rules"]
            row.required_permission = item["required_permission"]
            row.implementation_status = "implemented"
            continue
        db.add(BotSkill(enabled=True, implementation_status="implemented", config={}, **item))

    for item in BOT_PROFILES:
        row = (
            await db.execute(select(BotProfile).where(BotProfile.profile_key == item["profile_key"]))
        ).scalar_one_or_none()
        prompt = _default_system_prompt(item["name"], item["description"])
        if row:
            row.name = item["name"]
            row.description = item["description"]
            row.default_role = item["default_role"]
            row.allowed_skills = item["allowed_skills"]
            if not row.system_prompt:
                row.system_prompt = prompt
            continue
        db.add(BotProfile(system_prompt=prompt, status="enabled", config={}, **item))

    binding = (
        await db.execute(select(BotChannelBinding).where(BotChannelBinding.channel_key == "dingtalk_default"))
    ).scalar_one_or_none()
    if not binding:
        db.add(
            BotChannelBinding(
                channel_key="dingtalk_default",
                channel_type="dingtalk",
                channel_name="钉钉默认群",
                bot_profile_key="management_assistant_agent",
                external_id=None,
                binding_config={"source": "settings.dingtalk", "mode": "default"},
                status="active",
            )
        )
    await db.flush()


async def list_bot_runtime_overview(db: AsyncSession) -> dict[str, Any]:
    await ensure_bot_runtime_defaults(db)
    profile_count = (await db.execute(select(func.count(BotProfile.id)))).scalar_one() or 0
    skill_count = (await db.execute(select(func.count(BotSkill.id)).where(BotSkill.enabled.is_(True)))).scalar_one() or 0
    conversation_count = (await db.execute(select(func.count(BotConversation.id)))).scalar_one() or 0
    knowledge_count = (
        await db.execute(select(func.count(BotKnowledgeFile.id)).where(BotKnowledgeFile.status == "indexed"))
    ).scalar_one() or 0
    latest_run = (
        await db.execute(select(func.max(BotSkillRun.created_at)))
    ).scalar_one_or_none()
    return {
        "profiles": int(profile_count),
        "enabled_skills": int(skill_count),
        "conversations": int(conversation_count),
        "knowledge_files": int(knowledge_count),
        "latest_run_at": latest_run.isoformat() if latest_run else None,
    }


async def run_agent_chat(
    db: AsyncSession,
    *,
    profile_key: str,
    message: str,
    user: dict[str, Any],
    conversation_id: str | None = None,
    simulated_user_role: str | None = None,
) -> dict[str, Any]:
    """Run a test-console chat turn and persist every relevant event."""

    await ensure_bot_runtime_defaults(db)
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("消息不能为空")
    profile = (
        await db.execute(
            select(BotProfile).where(
                BotProfile.profile_key == profile_key,
                BotProfile.status == "enabled",
            )
        )
    ).scalar_one_or_none()
    if not profile:
        raise ValueError("机器人不存在或未启用")

    conversation = await _get_or_create_conversation(
        db,
        profile=profile,
        user=user,
        conversation_id=conversation_id,
        simulated_user_role=simulated_user_role,
        first_message=clean_message,
    )
    user_message = BotMessage(
        conversation_pk=conversation.id,
        role="user",
        content=clean_message,
        source="test_console",
        meta={"simulated_user_role": simulated_user_role or profile.default_role},
    )
    db.add(user_message)
    await db.flush()

    selected_skills = await _select_skills(db, profile, clean_message, user)
    skill_results: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    for skill in selected_skills:
        result = await _execute_skill(db, skill, profile, clean_message, conversation, user_message)
        skill_results.append(result)
        all_evidence.extend(result.get("evidence_records") or [])

    answer = await _synthesize_answer(
        db,
        profile=profile,
        message=clean_message,
        skill_results=skill_results,
        evidence_records=all_evidence,
    )
    assistant_message = BotMessage(
        conversation_pk=conversation.id,
        role="assistant",
        content=answer["content"],
        source="agent_runtime",
        meta={
            "skills": [item["skill_key"] for item in skill_results],
            "evidence_count": len(all_evidence),
            "llm_used": answer.get("llm_used", False),
            "risk_flags": answer.get("risk_flags", []),
        },
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        event_type="chat_test_turn",
        user=user,
        profile_key=profile.profile_key,
        conversation_id=conversation.conversation_id,
        payload={
            "message_length": len(clean_message),
            "skills": [item["skill_key"] for item in skill_results],
            "evidence_count": len(all_evidence),
        },
    )
    await db.flush()
    return {
        "conversation": _conversation_dict(conversation),
        "user_message": _message_dict(user_message),
        "assistant_message": _message_dict(assistant_message),
        "selected_skills": skill_results,
        "evidence_records": all_evidence[:20],
        "answer": answer,
    }


async def upload_knowledge_text(
    db: AsyncSession,
    *,
    title: str,
    text_content: str,
    category: str,
    user: dict[str, Any],
    file_name: str | None = None,
    content_type: str | None = None,
    source_type: str = "manual_upload",
) -> dict[str, Any]:
    clean_text = _normalize_text(text_content)
    clean_title = title.strip()[:200]
    if not clean_title:
        raise ValueError("知识标题不能为空")
    if len(clean_text) < 10:
        raise ValueError("知识内容过短，无法建立检索索引")
    now = datetime.now(timezone.utc)
    file = BotKnowledgeFile(
        file_id=f"KF-{uuid.uuid4().hex[:12]}",
        title=clean_title,
        file_name=file_name,
        content_type=content_type,
        source_type=source_type,
        category=(category or "general")[:50],
        text_content=clean_text[:300000],
        status="indexed",
        uploaded_by=_user_name(user),
        created_at=now,
        updated_at=now,
    )
    db.add(file)
    await db.flush()
    chunks = _chunk_text(clean_text)
    for index, chunk in enumerate(chunks):
        db.add(
            BotKnowledgeChunk(
                file_pk=file.id,
                chunk_index=index,
                title=clean_title,
                content=chunk,
                keywords=_extract_terms(chunk)[:20],
            )
        )
    file.chunk_count = len(chunks)
    file.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        event_type="knowledge_uploaded",
        user=user,
        payload={"file_id": file.file_id, "title": file.title, "chunk_count": file.chunk_count},
    )
    await db.flush()
    await db.refresh(file)
    return _knowledge_file_dict(file)


def extract_text_from_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return "\n".join(extractor.parts)


async def _get_or_create_conversation(
    db: AsyncSession,
    *,
    profile: BotProfile,
    user: dict[str, Any],
    conversation_id: str | None,
    simulated_user_role: str | None,
    first_message: str,
) -> BotConversation:
    if conversation_id:
        existing = (
            await db.execute(select(BotConversation).where(BotConversation.conversation_id == conversation_id))
        ).scalar_one_or_none()
        if existing:
            return existing
    title = re.sub(r"\s+", " ", first_message).strip()[:48] or "对话测试"
    conversation = BotConversation(
        conversation_id=f"BC-{uuid.uuid4().hex[:12]}",
        profile_key=profile.profile_key,
        title=title,
        simulated_user_role=simulated_user_role or profile.default_role,
        channel_type="test_console",
        status="active",
        created_by=_user_id(user),
        created_by_name=_user_name(user),
        meta={"entry": "bot_center"},
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _select_skills(
    db: AsyncSession,
    profile: BotProfile,
    message: str,
    user: dict[str, Any],
) -> list[BotSkill]:
    allowed = set(profile.allowed_skills or [])
    rows = (
        await db.execute(
            select(BotSkill).where(BotSkill.enabled.is_(True), BotSkill.skill_key.in_(allowed))
        )
    ).scalars().all()
    by_key = {row.skill_key: row for row in rows}
    text = message.lower()
    selected: list[str] = []
    market_context = _has_any(text, ["公安", "政数", "空间", "地图", "大数据", "电力", "运营商", "市场", "行业"])
    opportunity_context = _has_any(text, ["机会", "跟进", "重点关注", "销售线索", "客户切入", "近期"])
    if _has_any(text, ["标讯", "招投标", "投标", "采购", "预算", "项目机会"]) or (market_context and opportunity_context):
        selected.append("market.bidding_search")
        if _has_any(text, ["分析", "趋势", "分布", "统计", "月", "周", "年", "金额", "机会", "重点关注", "跟进"]):
            selected.append("market.bidding_analysis")
    if _has_any(text, ["政策", "市场", "政数", "大数据", "电力", "运营商", "空间", "地图", "行业动态"]):
        selected.append("market.policy_market_tracking")
    if _has_any(text, ["知识", "资料", "方案", "制度", "文档", "空间数据", "地址", "地图"]):
        selected.append("knowledge.search")
    if _has_any(text, ["周报", "本周", "上周", "部门", "总结", "归档"]):
        selected.append("report.weekly_archive_summary")
    if _has_any(text, ["商机", "签单", "回款", "销售", "预测", "跟进"]):
        selected.append("opportunity.followup_status")
    if _has_any(text, ["群发", "通知", "发到钉钉", "提醒大家", "提醒所有人"]):
        selected.append("dingtalk.broadcast")
    if not selected:
        selected = ["knowledge.search"]

    result = []
    seen = set()
    for key in selected:
        skill = by_key.get(key)
        if not skill or key in seen:
            continue
        if skill.required_permission and not has_permission(user, skill.required_permission):
            continue
        result.append(skill)
        seen.add(key)
    if not result and "knowledge.search" in by_key:
        result = [by_key["knowledge.search"]]
    return result


async def _execute_skill(
    db: AsyncSession,
    skill: BotSkill,
    profile: BotProfile,
    message: str,
    conversation: BotConversation,
    user_message: BotMessage,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    run = BotSkillRun(
        run_id=f"SR-{uuid.uuid4().hex[:12]}",
        conversation_pk=conversation.id,
        message_id=user_message.id,
        profile_key=profile.profile_key,
        skill_key=skill.skill_key,
        status="running",
        input_payload={"message": message},
        output_payload={},
        evidence_records=[],
        started_at=started,
    )
    db.add(run)
    await db.flush()
    tool = _SKILL_TOOLS.get(skill.skill_key, _skill_not_implemented)
    try:
        output, evidence, tool_calls = await tool(db, message, run)
        run.status = "success"
        run.output_payload = output
        run.evidence_records = evidence
        for call in tool_calls:
            call.skill_run_id = run.id
            db.add(call)
    except Exception as exc:  # noqa: BLE001
        output = {"message": "Skill 运行失败"}
        evidence = []
        run.status = "error"
        run.error_message = str(exc)[:1000]
    finished = datetime.now(timezone.utc)
    run.finished_at = finished
    run.duration_ms = int((finished - started).total_seconds() * 1000)
    await db.flush()
    return {
        "run_id": run.run_id,
        "skill_key": skill.skill_key,
        "skill_name": skill.name,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "output": output,
        "evidence_records": evidence,
        "error_message": run.error_message,
    }


async def _skill_knowledge_search(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    terms = _extract_terms(message)
    conditions = []
    for term in terms[:5]:
        pattern = f"%{term}%"
        conditions.append(BotKnowledgeChunk.content.ilike(pattern))
    stmt = select(BotKnowledgeChunk, BotKnowledgeFile).join(BotKnowledgeFile, BotKnowledgeChunk.file_pk == BotKnowledgeFile.id)
    if conditions:
        stmt = stmt.where(or_(*conditions))
    stmt = stmt.order_by(BotKnowledgeChunk.created_at.desc()).limit(8)
    rows = (await db.execute(stmt)).all()
    evidence = [
        {
            "evidence_id": f"KNOW-{file.file_id}-{chunk.chunk_index}",
            "source_type": "knowledge_file",
            "title": file.title,
            "source": file.file_name or file.source_type,
            "category": file.category,
            "snippet": _snippet(chunk.content, terms),
            "record_id": file.id,
        }
        for chunk, file in rows
    ]

    weekly_rows = (
        await db.execute(
            select(DepartmentWeeklyReport)
            .where(DepartmentWeeklyReport.status == "active")
            .order_by(DepartmentWeeklyReport.week_start.desc())
            .limit(5)
        )
    ).scalars().all()
    for report in weekly_rows:
        if terms and not any(term in (report.text_content or report.title or "") for term in terms):
            continue
        evidence.append({
            "evidence_id": f"WEEKLY-{report.id}",
            "source_type": "department_weekly_report",
            "title": report.title,
            "source": report.department,
            "category": "weekly_report",
            "snippet": _snippet(report.text_content or report.html_content, terms),
            "record_id": report.id,
        })
    return {"items": evidence[:10], "total": len(evidence)}, evidence[:10], [
        _tool_call("knowledge_keyword_search", "success", {"terms": terms}, {"count": len(evidence)})
    ]


async def _skill_bidding_search(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    terms = _extract_terms(message)
    conditions = [CrawlerItem.category == "bidding"]
    if terms:
        conditions.append(or_(*[
            CrawlerItem.title.ilike(f"%{term}%")
            | CrawlerItem.summary.ilike(f"%{term}%")
            | CrawlerItem.content.ilike(f"%{term}%")
            for term in terms[:5]
        ]))
    rows = (
        await db.execute(
            select(CrawlerItem)
            .where(*conditions)
            .order_by(CrawlerItem.relevance_score.desc().nullslast(), CrawlerItem.published_at.desc().nullslast())
            .limit(8)
        )
    ).scalars().all()
    items = [_crawler_evidence(row) for row in rows]
    return {"items": items, "total": len(items)}, items, [
        _tool_call("crawler_items.bidding_search", "success", {"terms": terms}, {"count": len(items)})
    ]


async def _skill_bidding_analysis(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    days = _period_days(message)
    start = date.today() - timedelta(days=days)
    rows = (
        await db.execute(
            select(CrawlerItem)
            .where(CrawlerItem.category == "bidding")
            .where((CrawlerItem.published_at >= start) | CrawlerItem.published_at.is_(None))
            .order_by(CrawlerItem.relevance_score.desc().nullslast(), CrawlerItem.created_at.desc())
            .limit(300)
        )
    ).scalars().all()
    region_counter = Counter((row.region or "未识别") for row in rows)
    notice_counter = Counter((row.notice_type or "未识别") for row in rows)
    keywords = Counter()
    for row in rows:
        for keyword in row.matched_keywords or []:
            keywords[str(keyword)] += 1
    amount_total = sum(float(row.amount_wan or 0) for row in rows)
    top_rows = sorted(rows, key=lambda row: (float(row.amount_wan or 0), float(row.relevance_score or 0)), reverse=True)[:8]
    evidence = [_crawler_evidence(row) for row in top_rows]
    output = {
        "range": {"start": start.isoformat(), "end": date.today().isoformat(), "days": days},
        "summary": {"total": len(rows), "amount_total_wan": round(amount_total, 2)},
        "distribution": {
            "regions": region_counter.most_common(8),
            "notice_types": notice_counter.most_common(8),
            "keywords": keywords.most_common(12),
        },
        "top_items": evidence,
    }
    return output, evidence, [_tool_call("crawler_items.bidding_analysis", "success", {"days": days}, {"count": len(rows)})]


async def _skill_policy_market(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    days = 365 if _has_any(message, ["年", "全年", "自然年", "26年", "2026"]) else 90
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)
    terms = _extract_terms(message)
    conditions = [CrawlerItem.category.in_(["policy", "news", "ai"])]
    if terms:
        conditions.append(or_(*[
            CrawlerItem.title.ilike(f"%{term}%")
            | CrawlerItem.summary.ilike(f"%{term}%")
            | CrawlerItem.content.ilike(f"%{term}%")
            for term in terms[:6]
        ]))
    rows = (
        await db.execute(
            select(CrawlerItem)
            .where(*conditions)
            .where(CrawlerItem.created_at >= start_dt.replace(tzinfo=None))
            .order_by(CrawlerItem.relevance_score.desc().nullslast(), CrawlerItem.published_at.desc().nullslast())
            .limit(12)
        )
    ).scalars().all()
    evidence = [_crawler_evidence(row) for row in rows]
    category_counter = Counter(row.category for row in rows)
    directions = _market_directions(rows)
    return {
        "signals": evidence,
        "distribution": category_counter.most_common(),
        "directions": directions,
        "range_days": days,
    }, evidence, [_tool_call("crawler_items.policy_market_tracking", "success", {"days": days, "terms": terms}, {"count": len(rows)})]


async def _skill_weekly_archive(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    terms = _extract_terms(message)
    rows = (
        await db.execute(
            select(DepartmentWeeklyReport)
            .where(DepartmentWeeklyReport.status == "active")
            .order_by(DepartmentWeeklyReport.week_start.desc(), DepartmentWeeklyReport.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    evidence = []
    for row in rows:
        haystack = f"{row.title} {row.department} {row.text_content or ''}"
        if terms and not any(term in haystack for term in terms):
            continue
        evidence.append({
            "evidence_id": f"WEEKLY-{row.id}",
            "source_type": "department_weekly_report",
            "title": row.title,
            "source": row.department,
            "category": "weekly_report",
            "week_start": row.week_start.isoformat() if row.week_start else None,
            "week_end": row.week_end.isoformat() if row.week_end else None,
            "snippet": _snippet(row.text_content or row.html_content, terms),
            "record_id": row.id,
        })
    return {"reports": evidence[:8], "total": len(evidence)}, evidence[:8], [
        _tool_call("department_weekly_reports.search", "success", {"terms": terms}, {"count": len(evidence)})
    ]


async def _skill_opportunity(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    terms = _extract_terms(message)
    conditions = []
    if terms:
        conditions.append(or_(*[
            OpportunityLead.project_name.ilike(f"%{term}%")
            | OpportunityLead.buyer.ilike(f"%{term}%")
            | OpportunityLead.summary.ilike(f"%{term}%")
            for term in terms[:5]
        ]))
    stmt = select(OpportunityLead)
    if conditions:
        stmt = stmt.where(*conditions)
    leads = (
        await db.execute(stmt.order_by(OpportunityLead.score.desc(), OpportunityLead.updated_at.desc()).limit(8))
    ).scalars().all()
    activities = (
        await db.execute(select(Activity).order_by(Activity.report_date.desc()).limit(8))
    ).scalars().all()
    evidence = [{
        "evidence_id": f"OPP-{lead.id}",
        "source_type": "opportunity_lead",
        "title": lead.project_name,
        "source": lead.buyer or lead.source,
        "category": "opportunity",
        "status": lead.status,
        "score": lead.score,
        "amount_wan": round(float(lead.budget or 0) / 10000, 2),
        "snippet": lead.summary or "",
        "record_id": lead.id,
    } for lead in leads]
    return {
        "leads": evidence,
        "recent_activity_count": len(activities),
        "boundary": "这里只跟进销售侧已维护或公开标讯转入的商机，不替销售编造预测。",
    }, evidence, [_tool_call("opportunity_leads.search", "success", {"terms": terms}, {"count": len(leads)})]


async def _skill_dingtalk_broadcast(
    db: AsyncSession,
    message: str,
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    cfg = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    configured = False
    mode = "未配置"
    if cfg:
        mode = cfg.delivery_mode or "webhook"
        configured = bool(decrypt_secret(cfg.webhook_url) or (cfg.app_key and decrypt_secret(cfg.app_secret)))
    output = {
        "requires_confirmation": True,
        "configured": configured,
        "delivery_mode": mode,
        "suggested_payload": {
            "title": "待确认机器人消息",
            "content": message[:1200],
            "message_type": "markdown",
            "target_type": "configured_group",
            "at_all": "所有人" in message or "@所有人" in message,
        },
        "policy": "测试对话只生成待确认草稿，不直接发送外部消息。",
    }
    return output, [], [_tool_call("dingtalk.broadcast.prepare", "success", {"message": message[:200]}, {"configured": configured})]


async def _skill_not_implemented(
    db: AsyncSession,  # noqa: ARG001
    message: str,  # noqa: ARG001
    run: BotSkillRun,  # noqa: ARG001
) -> tuple[dict[str, Any], list[dict[str, Any]], list[BotToolCall]]:
    return {"message": "该 Skill 暂未绑定执行器"}, [], []


_SKILL_TOOLS: dict[str, Callable[[AsyncSession, str, BotSkillRun], Any]] = {
    "knowledge.search": _skill_knowledge_search,
    "market.bidding_search": _skill_bidding_search,
    "market.bidding_analysis": _skill_bidding_analysis,
    "market.policy_market_tracking": _skill_policy_market,
    "report.weekly_archive_summary": _skill_weekly_archive,
    "opportunity.followup_status": _skill_opportunity,
    "dingtalk.broadcast": _skill_dingtalk_broadcast,
}


async def _synthesize_answer(
    db: AsyncSession,
    *,
    profile: BotProfile,
    message: str,
    skill_results: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
) -> dict[str, Any]:
    config = await get_runtime_llm_config(db)
    risk_flags = []
    if not evidence_records and not any(item["skill_key"] == "dingtalk.broadcast" for item in skill_results):
        risk_flags.append("no_evidence")
    if config.get("api_key"):
        try:
            service = await create_runtime_llm_service(db, timeout=45, scene="bot_agent_chat")
            response = await service.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            f"你是{profile.name}。只能基于给定 Skill 输出和证据回答；"
                            "没有证据时必须说明无法确定；外部发送动作必须提示需要确认。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"用户问题：{message}\n\n"
                            f"Skill 输出：{_json_compact(skill_results)}\n\n"
                            f"证据：{_json_compact(evidence_records[:12])}\n\n"
                            "请用中文给出简洁结论、依据和下一步建议。"
                        ),
                    },
                ],
                temperature=0.2,
            )
            content = ((response.get("choices") or [{}])[0].get("message") or {}).get("content")
            if content:
                return {"content": content.strip(), "llm_used": True, "risk_flags": risk_flags}
        except Exception as exc:  # noqa: BLE001
            risk_flags.append(f"llm_failed:{str(exc)[:80]}")
    return {
        "content": _fallback_answer(skill_results, evidence_records),
        "llm_used": False,
        "risk_flags": risk_flags,
    }


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


def _default_system_prompt(name: str, description: str) -> str:
    return (
        f"你是{name}。{description}\n"
        "回答必须来自受控 Skill、证据记录或明确的用户输入。"
        "不能编造金额、客户状态、时间、风险原因。"
        "涉及外部发送、删除、修改数据等动作时，必须要求确认并写入审计。"
    )


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean = _normalize_text(text)
    chunks = []
    start = 0
    while start < len(clean):
        chunk = clean[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += max(200, chunk_size - overlap)
    return chunks[:500]


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


def _conversation_dict(row: BotConversation) -> dict[str, Any]:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "profile_key": row.profile_key,
        "title": row.title,
        "simulated_user_role": row.simulated_user_role,
        "channel_type": row.channel_type,
        "status": row.status,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _message_dict(row: BotMessage) -> dict[str, Any]:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "content_type": row.content_type,
        "source": row.source,
        "meta": row.meta or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _knowledge_file_dict(row: BotKnowledgeFile) -> dict[str, Any]:
    return {
        "id": row.id,
        "file_id": row.file_id,
        "title": row.title,
        "file_name": row.file_name,
        "content_type": row.content_type,
        "source_type": row.source_type,
        "category": row.category,
        "status": row.status,
        "chunk_count": row.chunk_count,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


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
    import json

    return json.dumps(value, ensure_ascii=False, default=str)[:12000]
