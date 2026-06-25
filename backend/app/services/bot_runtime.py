"""Agent runtime for the Bot Center.

The runtime keeps the product agent-native without hiding business logic in a
prompt: every answer is backed by selected skills, controlled data tools,
skill-run records and evidence snippets.
"""

from __future__ import annotations

import asyncio
import hashlib
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
    BotActionApproval,
    BotChannelAdapter,
    BotChannelBinding,
    BotCollaborationRun,
    BotConversation,
    BotCompliancePolicy,
    BotEnvironment,
    BotEvaluationRun,
    BotFeedback,
    BotHandoff,
    BotInboundEvent,
    BotInboxItem,
    BotIntentCorrection,
    BotKnowledgeChunk,
    BotKnowledgeFile,
    BotKnowledgeSyncJob,
    BotMessage,
    BotProfile,
    BotReleaseVersion,
    BotSkill,
    BotSkillRun,
    BotTask,
    BotTaskRun,
    BotToolCall,
    BotTestCase,
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

BOT_CHANNEL_ADAPTERS: list[dict[str, Any]] = [
    {
        "adapter_key": "dingtalk_enterprise",
        "channel_type": "dingtalk",
        "name": "钉钉企业机器人",
        "event_mode": "webhook",
        "auth_scheme": "signed_webhook",
        "signing_required": True,
        "rate_limit_per_minute": 60,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": [5, 30, 120]},
        "capabilities": ["inbound_message", "markdown_reply", "broadcast", "at_user", "at_all"],
    },
    {
        "adapter_key": "feishu_enterprise",
        "channel_type": "feishu",
        "name": "飞书群机器人",
        "event_mode": "webhook",
        "auth_scheme": "signed_webhook",
        "signing_required": True,
        "rate_limit_per_minute": 60,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": [5, 30, 120]},
        "capabilities": ["inbound_message", "card_reply", "broadcast", "mention_user"],
    },
    {
        "adapter_key": "wechat_work_enterprise",
        "channel_type": "wechat_work",
        "name": "企业微信群机器人",
        "event_mode": "webhook",
        "auth_scheme": "signed_webhook",
        "signing_required": True,
        "rate_limit_per_minute": 60,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": [5, 30, 120]},
        "capabilities": ["inbound_message", "markdown_reply", "broadcast"],
    },
    {
        "adapter_key": "slack_enterprise",
        "channel_type": "slack",
        "name": "Slack Bot",
        "event_mode": "events_api",
        "auth_scheme": "oauth_scopes",
        "signing_required": True,
        "rate_limit_per_minute": 50,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": [3, 30, 300]},
        "capabilities": ["inbound_message", "thread_reply", "broadcast", "audit_log"],
    },
    {
        "adapter_key": "teams_enterprise",
        "channel_type": "teams",
        "name": "Microsoft Teams Bot",
        "event_mode": "bot_framework",
        "auth_scheme": "tenant_oauth",
        "signing_required": True,
        "rate_limit_per_minute": 40,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": [5, 30, 300]},
        "capabilities": ["inbound_message", "proactive_message", "handoff", "rate_limit_status"],
    },
]

BOT_ENVIRONMENTS: list[dict[str, Any]] = [
    {"environment_key": "test", "name": "测试环境", "is_default": False, "config": {"requires_release_gate": False}},
    {"environment_key": "staging", "name": "预发布环境", "is_default": False, "config": {"requires_release_gate": True}},
    {"environment_key": "prod", "name": "生产环境", "is_default": True, "config": {"requires_release_gate": True}},
]

BOT_COMPLIANCE_POLICIES: list[dict[str, Any]] = [
    {
        "policy_key": "default_sensitive_terms",
        "name": "敏感词与外发动作保护",
        "policy_type": "content_guard",
        "action": "warn",
        "rules": {"blocked_terms": ["密码", "密钥", "token", "身份证", "银行卡"], "require_approval_actions": ["broadcast", "external_api"]},
    },
    {
        "policy_key": "default_retention",
        "name": "对话与证据保留周期",
        "policy_type": "retention",
        "action": "audit",
        "rules": {"conversation_days": 365, "audit_days": 1095, "feedback_days": 730},
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

    for item in BOT_CHANNEL_ADAPTERS:
        row = (
            await db.execute(select(BotChannelAdapter).where(BotChannelAdapter.adapter_key == item["adapter_key"]))
        ).scalar_one_or_none()
        if row:
            row.name = item["name"]
            row.channel_type = item["channel_type"]
            row.event_mode = item["event_mode"]
            row.auth_scheme = item["auth_scheme"]
            row.signing_required = bool(item["signing_required"])
            row.rate_limit_per_minute = int(item["rate_limit_per_minute"])
            row.retry_policy = item["retry_policy"]
            row.capabilities = item["capabilities"]
            continue
        db.add(BotChannelAdapter(status="enabled", config={}, **item))

    for item in BOT_ENVIRONMENTS:
        row = (
            await db.execute(select(BotEnvironment).where(BotEnvironment.environment_key == item["environment_key"]))
        ).scalar_one_or_none()
        if row:
            row.name = item["name"]
            row.is_default = bool(item["is_default"])
            row.config = item["config"]
            continue
        db.add(BotEnvironment(status="enabled", **item))

    for item in BOT_COMPLIANCE_POLICIES:
        row = (
            await db.execute(select(BotCompliancePolicy).where(BotCompliancePolicy.policy_key == item["policy_key"]))
        ).scalar_one_or_none()
        if row:
            row.name = item["name"]
            row.policy_type = item["policy_type"]
            row.action = item["action"]
            row.rules = item["rules"]
            continue
        db.add(BotCompliancePolicy(status="enabled", **item))
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
    pending_approvals = (
        await db.execute(select(func.count(BotActionApproval.id)).where(BotActionApproval.status == "pending"))
    ).scalar_one() or 0
    active_tasks = (
        await db.execute(select(func.count(BotTask.id)).where(BotTask.status == "enabled"))
    ).scalar_one() or 0
    failed_evaluations = (
        await db.execute(select(func.count(BotEvaluationRun.id)).where(BotEvaluationRun.status == "failed"))
    ).scalar_one() or 0
    collaboration_runs = (await db.execute(select(func.count(BotCollaborationRun.id)))).scalar_one() or 0
    open_inbox = (await db.execute(select(func.count(BotInboxItem.id)).where(BotInboxItem.status == "open"))).scalar_one() or 0
    open_handoffs = (await db.execute(select(func.count(BotHandoff.id)).where(BotHandoff.status == "open"))).scalar_one() or 0
    enabled_adapters = (
        await db.execute(select(func.count(BotChannelAdapter.id)).where(BotChannelAdapter.status == "enabled"))
    ).scalar_one() or 0
    open_feedback = (await db.execute(select(func.count(BotFeedback.id)).where(BotFeedback.status == "open"))).scalar_one() or 0
    return {
        "profiles": int(profile_count),
        "enabled_skills": int(skill_count),
        "conversations": int(conversation_count),
        "knowledge_files": int(knowledge_count),
        "pending_approvals": int(pending_approvals),
        "active_tasks": int(active_tasks),
        "failed_evaluations": int(failed_evaluations),
        "collaboration_runs": int(collaboration_runs),
        "open_inbox": int(open_inbox),
        "open_handoffs": int(open_handoffs),
        "enabled_adapters": int(enabled_adapters),
        "open_feedback": int(open_feedback),
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
    channel_type: str = "test_console",
    message_source: str = "test_console",
    conversation_meta: dict[str, Any] | None = None,
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
        channel_type=channel_type,
        meta=conversation_meta,
    )
    user_message = BotMessage(
        conversation_pk=conversation.id,
        role="user",
        content=clean_message,
        source=message_source,
        meta={"simulated_user_role": simulated_user_role or profile.default_role, **(conversation_meta or {})},
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
    owner_profile_key: str | None = None,
    visibility_scope: str = "all_bots",
    tags: list[str] | None = None,
    review_status: str = "approved",
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
        review_status=review_status if review_status in {"pending", "approved", "rejected"} else "approved",
        visibility_scope=visibility_scope if visibility_scope in {"all_bots", "profile_only"} else "all_bots",
        owner_profile_key=owner_profile_key[:80] if owner_profile_key else None,
        tags=[str(tag).strip()[:40] for tag in (tags or []) if str(tag).strip()][:20],
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


async def upsert_bot_profile(
    db: AsyncSession,
    *,
    payload: dict[str, Any],
    user: dict[str, Any],
    profile_key: str | None = None,
) -> dict[str, Any]:
    """Create or update a bot profile from the operations console."""

    await ensure_bot_runtime_defaults(db)
    clean_key = (profile_key or str(payload.get("profile_key") or "")).strip()
    if not clean_key:
        clean_key = f"custom_agent_{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", clean_key):
        raise ValueError("机器人标识只能包含字母、数字、点、横线和下划线")
    name = str(payload.get("name") or "").strip()[:100]
    if not name:
        raise ValueError("机器人名称不能为空")
    status = str(payload.get("status") or "enabled").strip()
    if status not in {"enabled", "disabled"}:
        raise ValueError("机器人状态不支持")
    all_skills = {
        row.skill_key
        for row in (await db.execute(select(BotSkill))).scalars().all()
    }
    allowed_skills = [
        str(item).strip()
        for item in (payload.get("allowed_skills") or [])
        if str(item).strip() in all_skills
    ]
    row = (
        await db.execute(select(BotProfile).where(BotProfile.profile_key == clean_key))
    ).scalar_one_or_none()
    if not row:
        row = BotProfile(
            profile_key=clean_key,
            name=name,
            status=status,
            allowed_skills=allowed_skills,
            config={},
        )
        db.add(row)
    row.name = name
    row.description = str(payload.get("description") or "").strip()[:2000]
    row.default_role = str(payload.get("default_role") or "业务用户").strip()[:80]
    row.system_prompt = str(payload.get("system_prompt") or _default_system_prompt(row.name, row.description or "")).strip()[:8000]
    row.status = status
    row.allowed_skills = allowed_skills
    row.config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="profile_saved", user=user, profile_key=row.profile_key, payload={"name": row.name, "status": row.status})
    await db.flush()
    await db.refresh(row)
    return _profile_dict(row)


async def update_knowledge_metadata(
    db: AsyncSession,
    *,
    file_id: str,
    payload: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    row = (
        await db.execute(select(BotKnowledgeFile).where(BotKnowledgeFile.file_id == file_id))
    ).scalar_one_or_none()
    if not row:
        raise ValueError("知识文件不存在")
    for field in ("title", "category"):
        if field in payload:
            value = str(payload.get(field) or "").strip()
            if value:
                setattr(row, field, value[:200] if field == "title" else value[:50])
    if "status" in payload and payload["status"] in {"indexed", "archived"}:
        row.status = payload["status"]
    if "review_status" in payload and payload["review_status"] in {"pending", "approved", "rejected"}:
        row.review_status = payload["review_status"]
    if "visibility_scope" in payload and payload["visibility_scope"] in {"all_bots", "profile_only"}:
        row.visibility_scope = payload["visibility_scope"]
    if "owner_profile_key" in payload:
        owner = str(payload.get("owner_profile_key") or "").strip()
        row.owner_profile_key = owner[:80] if owner else None
    if "tags" in payload and isinstance(payload["tags"], list):
        row.tags = [str(tag).strip()[:40] for tag in payload["tags"] if str(tag).strip()][:20]
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="knowledge_metadata_updated", user=user, payload={"file_id": row.file_id, "status": row.status})
    await db.flush()
    await db.refresh(row)
    return _knowledge_file_dict(row)


async def handle_inbound_message(
    db: AsyncSession,
    *,
    channel_key: str,
    content: str,
    sender_id: str | None,
    sender_name: str | None,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process a real channel message through the bound bot profile."""

    await ensure_bot_runtime_defaults(db)
    clean = content.strip()
    if not clean:
        raise ValueError("入站消息不能为空")
    now = datetime.now(timezone.utc)
    binding = (
        await db.execute(
            select(BotChannelBinding).where(
                BotChannelBinding.channel_key == channel_key,
                BotChannelBinding.status == "active",
            )
        )
    ).scalar_one_or_none()
    if not binding:
        raise ValueError("未找到可用群聊绑定")

    adapter = await _adapter_for_channel(db, binding.channel_type)
    dedup_key, event_id = _inbound_event_keys(binding, sender_id, clean, raw_payload or {}, now)
    existing = (
        await db.execute(select(BotInboundEvent).where(BotInboundEvent.dedup_key == dedup_key))
    ).scalar_one_or_none()
    if existing and existing.status == "processed" and existing.result_payload:
        return existing.result_payload

    rate_limit = adapter.rate_limit_per_minute if adapter else 60
    minute_ago = now - timedelta(minutes=1)
    recent_count = (
        await db.execute(
            select(func.count(BotInboundEvent.id)).where(
                BotInboundEvent.channel_key == binding.channel_key,
                BotInboundEvent.received_at >= minute_ago,
            )
        )
    ).scalar_one() or 0
    if recent_count >= rate_limit:
        event = existing or BotInboundEvent(
            event_id=event_id,
            dedup_key=dedup_key,
            channel_key=binding.channel_key,
            channel_type=binding.channel_type,
            sender_id=sender_id,
            sender_name=sender_name,
            content=clean,
            status="rate_limited",
            raw_payload=raw_payload or {},
            received_at=now,
        )
        event.status = "rate_limited"
        event.error_message = "当前群聊消息过于密集，已按渠道限流策略暂停处理"
        if not existing:
            db.add(event)
        await db.flush()
        raise ValueError(event.error_message)

    compliance = await _check_compliance(db, clean)
    blocked = any(item.get("action") == "block" for item in compliance)
    event = existing or BotInboundEvent(
        event_id=event_id,
        dedup_key=dedup_key,
        channel_key=binding.channel_key,
        channel_type=binding.channel_type,
        sender_id=sender_id,
        sender_name=sender_name,
        content=clean,
        status="processing",
        raw_payload={**(raw_payload or {}), "compliance": compliance},
        received_at=now,
    )
    if not existing:
        db.add(event)
        await db.flush()
    if blocked:
        event.status = "blocked"
        event.error_message = "消息命中合规阻断策略，未交给机器人处理"
        event.processed_at = datetime.now(timezone.utc)
        await db.flush()
        raise ValueError(event.error_message)

    binding.last_seen_at = now
    external_thread_key = f"{binding.channel_type}:{binding.channel_key}:{sender_id or 'anonymous'}"
    conversation = await _find_channel_conversation(db, binding.bot_profile_key, external_thread_key)
    result = await run_agent_chat(
        db,
        profile_key=binding.bot_profile_key,
        message=clean,
        user={"id": None, "username": sender_name or "外部用户", "permissions": ["bot:view", "intelligence:view", "reports:view", "opportunities:view"]},
        conversation_id=conversation.conversation_id if conversation else None,
        simulated_user_role=sender_name or "群聊用户",
        channel_type=binding.channel_type,
        message_source=f"{binding.channel_type}_inbound",
        conversation_meta={
            "channel_key": binding.channel_key,
            "channel_name": binding.channel_name,
            "external_thread_key": external_thread_key,
            "sender_id": sender_id,
            "raw_payload": raw_payload or {},
            "compliance": compliance,
            "inbound_event_id": event.event_id,
        },
    )
    await _upsert_inbox_item(
        db,
        binding=binding,
        result=result,
        sender_name=sender_name,
        content=clean,
        compliance=compliance,
    )
    event.status = "processed"
    event.result_payload = result
    event.processed_at = datetime.now(timezone.utc)
    _audit(
        db,
        event_type="inbound_message_handled",
        user={"username": sender_name or "外部用户"},
        profile_key=binding.bot_profile_key,
        conversation_id=result["conversation"]["conversation_id"],
        payload={"channel_key": channel_key, "sender_id": sender_id},
    )
    await db.flush()
    return result


async def list_channel_adapters(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_bot_runtime_defaults(db)
    rows = (await db.execute(select(BotChannelAdapter).order_by(BotChannelAdapter.channel_type.asc()))).scalars().all()
    return [_channel_adapter_dict(row) for row in rows]


async def upsert_channel_adapter(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    await ensure_bot_runtime_defaults(db)
    adapter_key = str(payload.get("adapter_key") or "").strip()[:80]
    if not adapter_key:
        adapter_key = f"adapter_{uuid.uuid4().hex[:8]}"
    channel_type = str(payload.get("channel_type") or "").strip()[:40]
    name = str(payload.get("name") or "").strip()[:120]
    if not channel_type or not name:
        raise ValueError("渠道类型和适配器名称不能为空")
    row = (
        await db.execute(select(BotChannelAdapter).where(BotChannelAdapter.adapter_key == adapter_key))
    ).scalar_one_or_none()
    if not row:
        row = BotChannelAdapter(adapter_key=adapter_key, channel_type=channel_type, name=name)
        db.add(row)
    row.channel_type = channel_type
    row.name = name
    row.status = str(payload.get("status") or "enabled")[:20]
    row.event_mode = str(payload.get("event_mode") or "webhook")[:40]
    row.auth_scheme = str(payload.get("auth_scheme") or "signed_webhook")[:40]
    row.signing_required = bool(payload.get("signing_required", True))
    row.rate_limit_per_minute = max(1, min(int(payload.get("rate_limit_per_minute") or 60), 600))
    row.retry_policy = payload.get("retry_policy") if isinstance(payload.get("retry_policy"), dict) else {"max_attempts": 3}
    row.capabilities = [str(item).strip()[:60] for item in (payload.get("capabilities") or []) if str(item).strip()][:30]
    row.config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="channel_adapter_saved", user=user, payload={"adapter_key": row.adapter_key, "channel_type": row.channel_type})
    await db.flush()
    await db.refresh(row)
    return _channel_adapter_dict(row)


async def list_inbox_items(db: AsyncSession, *, status: str | None = None) -> dict[str, Any]:
    conditions = []
    if status:
        conditions.append(BotInboxItem.status == status)
    total = (await db.execute(select(func.count(BotInboxItem.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(select(BotInboxItem).where(*conditions).order_by(BotInboxItem.updated_at.desc()).limit(50))
    ).scalars().all()
    return {"total": int(total), "items": [_inbox_item_dict(row) for row in rows]}


async def update_inbox_item(db: AsyncSession, *, inbox_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(BotInboxItem).where(BotInboxItem.inbox_id == inbox_id))
    ).scalar_one_or_none()
    if not row:
        raise ValueError("收件箱事项不存在")
    if "status" in payload and payload["status"] in {"open", "processing", "handoff", "resolved", "ignored"}:
        row.status = payload["status"]
    if "priority" in payload and payload["priority"] in {"P0", "P1", "P2", "P3"}:
        row.priority = payload["priority"]
    if "owner_name" in payload:
        row.owner_name = str(payload.get("owner_name") or "").strip()[:120] or None
    if "resolution_summary" in payload:
        row.resolution_summary = str(payload.get("resolution_summary") or "").strip()[:2000] or None
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="inbox_item_updated", user=user, profile_key=row.profile_key, conversation_id=row.conversation_id, payload={"inbox_id": inbox_id, "status": row.status})
    await db.flush()
    await db.refresh(row)
    return _inbox_item_dict(row)


async def create_handoff(db: AsyncSession, *, inbox_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    inbox = (
        await db.execute(select(BotInboxItem).where(BotInboxItem.inbox_id == inbox_id))
    ).scalar_one_or_none()
    if not inbox:
        raise ValueError("收件箱事项不存在")
    assignee = str(payload.get("assignee_name") or "").strip()[:120]
    if not assignee:
        raise ValueError("接管负责人不能为空")
    row = BotHandoff(
        handoff_id=f"HO-{uuid.uuid4().hex[:12]}",
        inbox_id=inbox.inbox_id,
        conversation_id=inbox.conversation_id,
        assignee_name=assignee,
        reason=str(payload.get("reason") or "").strip()[:2000] or None,
        requested_by_name=_user_name(user),
        status="open",
    )
    db.add(row)
    inbox.status = "handoff"
    inbox.owner_name = assignee
    inbox.handoff_required = True
    inbox.handoff_reason = row.reason
    inbox.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="handoff_created", user=user, profile_key=inbox.profile_key, conversation_id=inbox.conversation_id, payload={"handoff_id": row.handoff_id, "assignee": assignee})
    await db.flush()
    await db.refresh(row)
    return _handoff_dict(row)


async def list_handoffs(db: AsyncSession, *, status: str | None = None) -> dict[str, Any]:
    conditions = []
    if status:
        conditions.append(BotHandoff.status == status)
    total = (await db.execute(select(func.count(BotHandoff.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(select(BotHandoff).where(*conditions).order_by(BotHandoff.created_at.desc()).limit(50))
    ).scalars().all()
    return {"total": int(total), "items": [_handoff_dict(row) for row in rows]}


async def create_bot_task(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    await ensure_bot_runtime_defaults(db)
    title = str(payload.get("title") or "").strip()[:160]
    if not title:
        raise ValueError("任务名称不能为空")
    task_type = str(payload.get("task_type") or "custom_prompt").strip()
    profile_key = str(payload.get("profile_key") or "management_assistant_agent").strip()
    task = BotTask(
        task_id=f"BT-{uuid.uuid4().hex[:12]}",
        title=title,
        task_type=task_type,
        profile_key=profile_key,
        status=str(payload.get("status") or "enabled")[:20],
        schedule_type=str(payload.get("schedule_type") or "manual")[:30],
        schedule_config=payload.get("schedule_config") if isinstance(payload.get("schedule_config"), dict) else {},
        input_payload=payload.get("input_payload") if isinstance(payload.get("input_payload"), dict) else {},
        created_by_name=_user_name(user),
    )
    db.add(task)
    _audit(db, event_type="task_created", user=user, profile_key=profile_key, payload={"task_id": task.task_id, "task_type": task.task_type})
    await db.flush()
    await db.refresh(task)
    return _task_dict(task)


async def run_bot_task_now(db: AsyncSession, *, task_id: str, user: dict[str, Any]) -> dict[str, Any]:
    task = (
        await db.execute(select(BotTask).where(BotTask.task_id == task_id))
    ).scalar_one_or_none()
    if not task:
        raise ValueError("任务不存在")
    prompt = _task_prompt(task)
    started = datetime.now(timezone.utc)
    run = BotTaskRun(
        run_id=f"BTR-{uuid.uuid4().hex[:12]}",
        task_id=task.task_id,
        profile_key=task.profile_key,
        trigger_type="manual",
        status="running",
        started_at=started,
    )
    db.add(run)
    await db.flush()
    try:
        result = await run_agent_chat(
            db,
            profile_key=task.profile_key,
            message=prompt,
            user=user,
            simulated_user_role="任务调度器",
            channel_type="task",
            message_source="bot_task",
            conversation_meta={"task_id": task.task_id, "task_type": task.task_type, "task_run_id": run.run_id},
        )
        finished = datetime.now(timezone.utc)
        run.status = "completed"
        run.finished_at = finished
        run.duration_ms = int((finished - started).total_seconds() * 1000)
        run.result_payload = {
            "conversation": result["conversation"],
            "answer": result["assistant_message"]["content"],
            "skills": [item["skill_key"] for item in result.get("selected_skills", [])],
            "evidence_count": len(result.get("evidence_records") or []),
        }
        task.last_run_at = started
        task.result_payload = {**run.result_payload, "task_run_id": run.run_id}
        task.updated_at = finished
        _audit(db, event_type="task_run", user=user, profile_key=task.profile_key, conversation_id=result["conversation"]["conversation_id"], payload={"task_id": task.task_id, "run_id": run.run_id})
        await db.flush()
        await db.refresh(task)
        return _task_dict(task)
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        run.status = "failed"
        run.finished_at = finished
        run.duration_ms = int((finished - started).total_seconds() * 1000)
        run.error_message = str(exc)[:1000]
        task.last_run_at = started
        task.result_payload = {"task_run_id": run.run_id, "status": "failed", "error_message": run.error_message}
        task.updated_at = finished
        await db.flush()
        raise


async def list_task_runs(db: AsyncSession, *, task_id: str | None = None) -> dict[str, Any]:
    conditions = []
    if task_id:
        conditions.append(BotTaskRun.task_id == task_id)
    total = (await db.execute(select(func.count(BotTaskRun.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(select(BotTaskRun).where(*conditions).order_by(BotTaskRun.started_at.desc()).limit(50))
    ).scalars().all()
    return {"total": int(total), "items": [_task_run_dict(row) for row in rows]}


async def create_action_approval(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()[:160]
    if not title:
        raise ValueError("动作标题不能为空")
    action_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    row = BotActionApproval(
        action_id=f"BA-{uuid.uuid4().hex[:12]}",
        action_type=str(payload.get("action_type") or "dingtalk_broadcast")[:50],
        title=title,
        profile_key=str(payload.get("profile_key") or "")[:80] or None,
        status="pending",
        payload=action_payload,
        requested_by_name=_user_name(user),
    )
    db.add(row)
    _audit(db, event_type="action_approval_created", user=user, profile_key=row.profile_key, payload={"action_id": row.action_id, "action_type": row.action_type})
    await db.flush()
    await db.refresh(row)
    return _approval_dict(row)


async def decide_action_approval(db: AsyncSession, *, action_id: str, decision: str, user: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(BotActionApproval).where(BotActionApproval.action_id == action_id))
    ).scalar_one_or_none()
    if not row:
        raise ValueError("审批动作不存在")
    if row.status not in {"pending", "approved"} and decision != "execute":
        raise ValueError("当前状态不能审批")
    now = datetime.now(timezone.utc)
    if decision == "approve":
        row.status = "approved"
        row.decided_by_name = _user_name(user)
        row.decided_at = now
    elif decision == "reject":
        row.status = "rejected"
        row.decided_by_name = _user_name(user)
        row.decided_at = now
    elif decision == "execute":
        if row.status != "approved":
            raise ValueError("动作必须先审批通过才能执行")
        row.status = "executed"
        row.executed_at = now
        row.result_payload = {"message": "动作已确认，外部执行由对应发送接口完成", "payload": row.payload}
    else:
        raise ValueError("审批动作不支持")
    row.updated_at = now
    _audit(db, event_type=f"action_{decision}", user=user, profile_key=row.profile_key, payload={"action_id": row.action_id})
    await db.flush()
    await db.refresh(row)
    return _approval_dict(row)


async def create_test_case(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()[:120]
    input_text = str(payload.get("input_text") or "").strip()
    if not name or not input_text:
        raise ValueError("测试用例名称和问题不能为空")
    row = BotTestCase(
        name=name,
        profile_key=str(payload.get("profile_key") or "management_assistant_agent")[:80],
        input_text=input_text,
        conversation_turns=payload.get("conversation_turns") if isinstance(payload.get("conversation_turns"), list) else [],
        expected_skills=[str(item) for item in (payload.get("expected_skills") or [])],
        expected_contains=[str(item) for item in (payload.get("expected_contains") or [])],
        required_evidence=bool(payload.get("required_evidence", True)),
        priority=str(payload.get("priority") or "P1")[:20],
        created_by_name=_user_name(user),
        status="active",
    )
    db.add(row)
    _audit(db, event_type="test_case_created", user=user, profile_key=row.profile_key, payload={"name": row.name})
    await db.flush()
    await db.refresh(row)
    return _test_case_dict(row)


async def run_test_case(db: AsyncSession, *, case_id: int, user: dict[str, Any]) -> dict[str, Any]:
    case = (
        await db.execute(select(BotTestCase).where(BotTestCase.id == case_id))
    ).scalar_one_or_none()
    if not case:
        raise ValueError("测试用例不存在")
    turns = case.conversation_turns or []
    result = None
    conversation_id = None
    if turns:
        for index, turn in enumerate(turns[:8]):
            text = str(turn.get("input") if isinstance(turn, dict) else turn).strip()
            if not text:
                continue
            result = await run_agent_chat(
                db,
                profile_key=case.profile_key,
                message=text,
                conversation_id=conversation_id,
                user=user,
                simulated_user_role="评测用户",
                channel_type="evaluation",
                message_source="bot_evaluation",
                conversation_meta={"test_case_id": case.id, "turn_index": index},
            )
            conversation_id = result["conversation"]["conversation_id"]
    if result is None:
        result = await run_agent_chat(
            db,
            profile_key=case.profile_key,
            message=case.input_text,
            user=user,
            simulated_user_role="评测用户",
            channel_type="evaluation",
            message_source="bot_evaluation",
            conversation_meta={"test_case_id": case.id},
        )
    selected = [item["skill_key"] for item in result.get("selected_skills", [])]
    answer = result["assistant_message"]["content"]
    missing_skills = [skill for skill in (case.expected_skills or []) if skill not in selected]
    missing_text = [text for text in (case.expected_contains or []) if text not in answer]
    evidence_count = len(result.get("evidence_records") or [])
    failures = []
    if missing_skills:
        failures.append({"type": "missing_skills", "items": missing_skills})
    if missing_text:
        failures.append({"type": "missing_text", "items": missing_text})
    if case.required_evidence and evidence_count == 0:
        failures.append({"type": "missing_evidence", "items": []})
    passed = not failures
    score = 1.0 if passed else max(0.0, 1.0 - 0.25 * len(failures))
    run = BotEvaluationRun(
        run_id=f"EVR-{uuid.uuid4().hex[:12]}",
        test_case_id=case.id,
        profile_key=case.profile_key,
        status="passed" if passed else "failed",
        score=score,
        result_payload={
            "selected_skills": selected,
            "evidence_count": evidence_count,
            "failures": failures,
            "conversation": result["conversation"],
        },
        created_by_name=_user_name(user),
    )
    db.add(run)
    case.last_result = run.result_payload | {"status": run.status, "score": run.score}
    case.last_run_at = datetime.now(timezone.utc)
    _audit(db, event_type="test_case_run", user=user, profile_key=case.profile_key, payload={"case_id": case.id, "status": run.status, "score": run.score})
    await db.flush()
    await db.refresh(run)
    await db.refresh(case)
    return {"test_case": _test_case_dict(case), "run": _evaluation_run_dict(run)}


async def create_intent_correction(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    phrase = str(payload.get("phrase") or "").strip()[:200]
    expected_skills = [str(item).strip() for item in (payload.get("expected_skills") or []) if str(item).strip()]
    if not phrase or not expected_skills:
        raise ValueError("纠错短语和期望 Skill 不能为空")
    row = BotIntentCorrection(
        phrase=phrase,
        profile_key=str(payload.get("profile_key") or "")[:80] or None,
        expected_skills=expected_skills[:10],
        notes=str(payload.get("notes") or "").strip()[:1000] or None,
        created_by_name=_user_name(user),
    )
    db.add(row)
    _audit(db, event_type="intent_correction_created", user=user, profile_key=row.profile_key, payload={"phrase": phrase, "expected_skills": expected_skills})
    await db.flush()
    await db.refresh(row)
    return _intent_correction_dict(row)


async def run_collaboration(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("input_text") or "").strip()
    if not question:
        raise ValueError("协作问题不能为空")
    participants = [str(item).strip() for item in (payload.get("participant_profiles") or []) if str(item).strip()]
    if not participants:
        participants = ["market_intelligence_agent", "daily_report_agent", "opportunity_followup_agent"]
    lead = str(payload.get("lead_profile_key") or "management_assistant_agent").strip()
    run = BotCollaborationRun(
        run_id=f"COL-{uuid.uuid4().hex[:12]}",
        title=str(payload.get("title") or question[:60] or "多机器人协作")[:160],
        lead_profile_key=lead,
        participant_profiles=participants,
        input_text=question,
        status="running",
        result_payload={},
        evidence_records=[],
        created_by_name=_user_name(user),
    )
    db.add(run)
    await db.flush()
    answers = []
    evidence = []
    for profile_key in participants:
        try:
            item = await run_agent_chat(
                db,
                profile_key=profile_key,
                message=question,
                user=user,
                simulated_user_role="协作任务",
                channel_type="collaboration",
                message_source="bot_collaboration",
                conversation_meta={"collaboration_run_id": run.run_id, "participant": profile_key},
            )
            answers.append({"profile_key": profile_key, "answer": item["assistant_message"]["content"], "conversation": item["conversation"]})
            evidence.extend(item.get("evidence_records") or [])
        except Exception as exc:  # noqa: BLE001
            answers.append({"profile_key": profile_key, "error": str(exc)[:500]})
    run.status = "completed"
    run.evidence_records = evidence[:30]
    run.result_payload = {
        "answers": answers,
        "summary": _fallback_answer(
            [{"skill_key": "collaboration", "skill_name": "多机器人协作", "evidence_records": evidence}],
            evidence,
        ),
    }
    run.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="collaboration_run", user=user, profile_key=lead, payload={"run_id": run.run_id, "participants": participants})
    await db.flush()
    await db.refresh(run)
    return _collaboration_dict(run)


async def list_release_versions(db: AsyncSession, *, profile_key: str | None = None) -> dict[str, Any]:
    await ensure_bot_runtime_defaults(db)
    conditions = []
    if profile_key:
        conditions.append(BotReleaseVersion.profile_key == profile_key)
    total = (await db.execute(select(func.count(BotReleaseVersion.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(select(BotReleaseVersion).where(*conditions).order_by(BotReleaseVersion.created_at.desc()).limit(50))
    ).scalars().all()
    return {"total": int(total), "items": [_release_version_dict(row) for row in rows]}


async def create_release_version(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    await ensure_bot_runtime_defaults(db)
    profile_key = str(payload.get("profile_key") or "management_assistant_agent").strip()
    profile = (
        await db.execute(select(BotProfile).where(BotProfile.profile_key == profile_key))
    ).scalar_one_or_none()
    if not profile:
        raise ValueError("机器人 Profile 不存在")
    latest_version = (
        await db.execute(select(func.max(BotReleaseVersion.version)).where(BotReleaseVersion.profile_key == profile_key))
    ).scalar_one() or 0
    skills = (
        await db.execute(select(BotSkill).where(BotSkill.skill_key.in_(profile.allowed_skills or [])))
    ).scalars().all()
    release = BotReleaseVersion(
        version_id=f"BRV-{uuid.uuid4().hex[:12]}",
        profile_key=profile_key,
        version=int(latest_version) + 1,
        status="draft",
        environment_key=str(payload.get("environment_key") or "prod")[:40],
        payload={
            "profile": _profile_dict(profile),
            "skills": [_skill_dict(skill) for skill in skills],
            "change_note": str(payload.get("change_note") or "").strip()[:2000],
        },
        created_by_name=_user_name(user),
    )
    db.add(release)
    _audit(db, event_type="release_created", user=user, profile_key=profile_key, payload={"version_id": release.version_id})
    await db.flush()
    await db.refresh(release)
    return _release_version_dict(release)


async def publish_release_version(db: AsyncSession, *, version_id: str, user: dict[str, Any], force: bool = False) -> dict[str, Any]:
    release = (
        await db.execute(select(BotReleaseVersion).where(BotReleaseVersion.version_id == version_id))
    ).scalar_one_or_none()
    if not release:
        raise ValueError("发布版本不存在")
    cases = (
        await db.execute(select(BotTestCase).where(BotTestCase.profile_key == release.profile_key, BotTestCase.status == "active"))
    ).scalars().all()
    runs = []
    failed = 0
    for case in cases[:20]:
        result = await run_test_case(db, case_id=case.id, user=user)
        runs.append(result["run"])
        if result["run"]["status"] != "passed":
            failed += 1
    release.test_summary = {"total": len(runs), "failed": failed, "forced": force}
    if failed and not force:
        release.status = "blocked"
        await db.flush()
        await db.refresh(release)
        raise ValueError("发布门禁未通过：存在失败评测")
    now = datetime.now(timezone.utc)
    previous = (
        await db.execute(
            select(BotReleaseVersion).where(
                BotReleaseVersion.profile_key == release.profile_key,
                BotReleaseVersion.environment_key == release.environment_key,
                BotReleaseVersion.status == "released",
            )
        )
    ).scalars().all()
    for item in previous:
        item.status = "superseded"
        item.updated_at = now
    release.status = "released"
    release.published_at = now
    release.updated_at = now
    _audit(db, event_type="release_published", user=user, profile_key=release.profile_key, payload={"version_id": release.version_id, "failed": failed})
    await db.flush()
    await db.refresh(release)
    return _release_version_dict(release)


async def rollback_release_version(db: AsyncSession, *, version_id: str, user: dict[str, Any]) -> dict[str, Any]:
    release = (
        await db.execute(select(BotReleaseVersion).where(BotReleaseVersion.version_id == version_id))
    ).scalar_one_or_none()
    if not release:
        raise ValueError("发布版本不存在")
    release.status = "rolled_back"
    release.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="release_rolled_back", user=user, profile_key=release.profile_key, payload={"version_id": version_id})
    await db.flush()
    await db.refresh(release)
    return _release_version_dict(release)


async def create_feedback(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    rating = str(payload.get("rating") or "").strip()
    if rating not in {"helpful", "unhelpful", "unsafe", "wrong"}:
        raise ValueError("反馈类型不支持")
    row = BotFeedback(
        feedback_id=f"FB-{uuid.uuid4().hex[:12]}",
        conversation_id=str(payload.get("conversation_id") or "").strip()[:80] or None,
        message_id=int(payload["message_id"]) if str(payload.get("message_id") or "").isdigit() else None,
        profile_key=str(payload.get("profile_key") or "").strip()[:80] or None,
        rating=rating,
        reason=str(payload.get("reason") or "").strip()[:120] or None,
        comment=str(payload.get("comment") or "").strip()[:2000] or None,
        status="open",
        created_by_name=_user_name(user),
    )
    db.add(row)
    _audit(db, event_type="feedback_created", user=user, profile_key=row.profile_key, conversation_id=row.conversation_id, payload={"feedback_id": row.feedback_id, "rating": rating})
    await db.flush()
    await db.refresh(row)
    return _feedback_dict(row)


async def list_feedback(db: AsyncSession, *, status: str | None = None) -> dict[str, Any]:
    conditions = []
    if status:
        conditions.append(BotFeedback.status == status)
    total = (await db.execute(select(func.count(BotFeedback.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(select(BotFeedback).where(*conditions).order_by(BotFeedback.created_at.desc()).limit(50))
    ).scalars().all()
    return {"total": int(total), "items": [_feedback_dict(row) for row in rows]}


async def list_knowledge_sync_jobs(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(BotKnowledgeSyncJob).order_by(BotKnowledgeSyncJob.created_at.desc()).limit(50))).scalars().all()
    return {"total": len(rows), "items": [_knowledge_sync_job_dict(row) for row in rows]}


async def create_knowledge_sync_job(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()[:160]
    source_type = str(payload.get("source_type") or "manual_text").strip()[:50]
    if not name:
        raise ValueError("同步任务名称不能为空")
    row = BotKnowledgeSyncJob(
        job_id=f"KS-{uuid.uuid4().hex[:12]}",
        name=name,
        source_type=source_type,
        category=str(payload.get("category") or "general")[:50],
        schedule_type=str(payload.get("schedule_type") or "manual")[:30],
        source_config=payload.get("source_config") if isinstance(payload.get("source_config"), dict) else {},
        status=str(payload.get("status") or "enabled")[:30],
        created_by_name=_user_name(user),
    )
    db.add(row)
    _audit(db, event_type="knowledge_sync_created", user=user, payload={"job_id": row.job_id, "source_type": source_type})
    await db.flush()
    await db.refresh(row)
    return _knowledge_sync_job_dict(row)


async def run_knowledge_sync_job(db: AsyncSession, *, job_id: str, user: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(BotKnowledgeSyncJob).where(BotKnowledgeSyncJob.job_id == job_id))
    ).scalar_one_or_none()
    if not row:
        raise ValueError("知识同步任务不存在")
    config = row.source_config or {}
    now = datetime.now(timezone.utc)
    if row.source_type == "manual_text":
        text = str(config.get("text_content") or "").strip()
        if len(text) < 10:
            raise ValueError("手动文本同步任务缺少可入库内容")
        saved = await upload_knowledge_text(
            db,
            title=str(config.get("title") or row.name),
            text_content=text,
            category=row.category,
            user=user,
            source_type="sync_manual_text",
            tags=["sync", row.source_type],
        )
        row.result_payload = {"status": "completed", "file_id": saved["file_id"], "message": "知识已同步入库"}
    else:
        row.result_payload = {"status": "needs_adapter", "message": "该来源已建档，需接入对应连接器后自动同步"}
    row.last_run_at = now
    row.updated_at = now
    _audit(db, event_type="knowledge_sync_run", user=user, payload={"job_id": row.job_id, "status": row.result_payload.get("status")})
    await db.flush()
    await db.refresh(row)
    return _knowledge_sync_job_dict(row)


async def list_environments(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_bot_runtime_defaults(db)
    rows = (await db.execute(select(BotEnvironment).order_by(BotEnvironment.id.asc()))).scalars().all()
    return [_environment_dict(row) for row in rows]


async def list_compliance_policies(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_bot_runtime_defaults(db)
    rows = (await db.execute(select(BotCompliancePolicy).order_by(BotCompliancePolicy.id.asc()))).scalars().all()
    return [_compliance_policy_dict(row) for row in rows]


async def upsert_compliance_policy(db: AsyncSession, *, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    policy_key = str(payload.get("policy_key") or "").strip()[:80] or f"policy_{uuid.uuid4().hex[:8]}"
    name = str(payload.get("name") or "").strip()[:120]
    if not name:
        raise ValueError("策略名称不能为空")
    row = (
        await db.execute(select(BotCompliancePolicy).where(BotCompliancePolicy.policy_key == policy_key))
    ).scalar_one_or_none()
    if not row:
        row = BotCompliancePolicy(policy_key=policy_key, name=name, policy_type=str(payload.get("policy_type") or "content_guard")[:50])
        db.add(row)
    row.name = name
    row.policy_type = str(payload.get("policy_type") or row.policy_type)[:50]
    row.status = str(payload.get("status") or "enabled")[:30]
    row.action = str(payload.get("action") or "warn")[:40]
    row.rules = payload.get("rules") if isinstance(payload.get("rules"), dict) else {}
    row.created_by_name = row.created_by_name or _user_name(user)
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, event_type="compliance_policy_saved", user=user, payload={"policy_key": row.policy_key, "action": row.action})
    await db.flush()
    await db.refresh(row)
    return _compliance_policy_dict(row)


async def bot_observability_summary(db: AsyncSession) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    total_runs = (await db.execute(select(func.count(BotSkillRun.id)).where(BotSkillRun.created_at >= since))).scalar_one() or 0
    failed_runs = (
        await db.execute(select(func.count(BotSkillRun.id)).where(BotSkillRun.created_at >= since, BotSkillRun.status != "success"))
    ).scalar_one() or 0
    avg_duration = (
        await db.execute(select(func.avg(BotSkillRun.duration_ms)).where(BotSkillRun.created_at >= since))
    ).scalar_one() or 0
    inbound_failed = (
        await db.execute(select(func.count(BotInboundEvent.id)).where(BotInboundEvent.received_at >= since, BotInboundEvent.status.in_(["failed", "blocked", "rate_limited"])))
    ).scalar_one() or 0
    feedback_open = (await db.execute(select(func.count(BotFeedback.id)).where(BotFeedback.status == "open"))).scalar_one() or 0
    return {
        "range_days": 7,
        "skill_runs": int(total_runs),
        "failed_skill_runs": int(failed_runs),
        "avg_skill_duration_ms": round(float(avg_duration or 0), 2),
        "failed_inbound_events": int(inbound_failed),
        "open_feedback": int(feedback_open),
    }


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
    channel_type: str = "test_console",
    meta: dict[str, Any] | None = None,
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
        channel_type=channel_type,
        status="active",
        created_by=_user_id(user),
        created_by_name=_user_name(user),
        meta={"entry": "bot_center", **(meta or {})},
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _find_channel_conversation(
    db: AsyncSession,
    profile_key: str,
    external_thread_key: str,
) -> BotConversation | None:
    rows = (
        await db.execute(
            select(BotConversation)
            .where(BotConversation.profile_key == profile_key, BotConversation.status == "active")
            .order_by(BotConversation.updated_at.desc())
            .limit(50)
        )
    ).scalars().all()
    for row in rows:
        if (row.meta or {}).get("external_thread_key") == external_thread_key:
            return row
    return None


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
    corrections = (
        await db.execute(
            select(BotIntentCorrection).where(BotIntentCorrection.status == "active")
        )
    ).scalars().all()
    for correction in corrections:
        if correction.profile_key and correction.profile_key != profile.profile_key:
            continue
        if correction.phrase and correction.phrase.lower() in text:
            selected.extend(correction.expected_skills or [])
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
    now = datetime.now(timezone.utc)
    stmt = (
        select(BotKnowledgeChunk, BotKnowledgeFile)
        .join(BotKnowledgeFile, BotKnowledgeChunk.file_pk == BotKnowledgeFile.id)
        .where(
            BotKnowledgeFile.status == "indexed",
            BotKnowledgeFile.review_status == "approved",
            (BotKnowledgeFile.expires_at.is_(None)) | (BotKnowledgeFile.expires_at > now),
        )
    )
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
        "review_status": row.review_status,
        "visibility_scope": row.visibility_scope,
        "owner_profile_key": row.owner_profile_key,
        "tags": row.tags or [],
        "version": row.version,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "chunk_count": row.chunk_count,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _profile_dict(row: BotProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "profile_key": row.profile_key,
        "name": row.name,
        "description": row.description,
        "system_prompt": row.system_prompt,
        "default_role": row.default_role,
        "status": row.status,
        "allowed_skills": row.allowed_skills or [],
        "config": row.config or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _skill_dict(row: BotSkill) -> dict[str, Any]:
    return {
        "id": row.id,
        "skill_key": row.skill_key,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "trigger_scenarios": row.trigger_scenarios or [],
        "input_contract": row.input_contract or {},
        "output_contract": row.output_contract or {},
        "evidence_rules": row.evidence_rules or {},
        "required_permission": row.required_permission,
        "enabled": row.enabled,
        "implementation_status": row.implementation_status,
        "config": row.config or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _task_prompt(task: BotTask) -> str:
    payload = task.input_payload or {}
    custom_prompt = str(payload.get("prompt") or "").strip()
    if custom_prompt:
        return custom_prompt
    if task.task_type == "market_digest":
        return "请基于最新标讯、政策与市场线索，生成一份可发给管理者的市场洞察简报，必须列出证据和下一步动作。"
    if task.task_type == "weekly_summary":
        return "请基于部门周报归档，总结本周部门发生了什么、风险是什么、下周建议关注什么。"
    if task.task_type == "opportunity_followup":
        return "请检查当前商机进展，找出需要销售跟进、签单预测或回款预测关注的事项。"
    return f"请执行机器人任务：{task.title}"


def _task_dict(row: BotTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "title": row.title,
        "task_type": row.task_type,
        "profile_key": row.profile_key,
        "status": row.status,
        "schedule_type": row.schedule_type,
        "schedule_config": row.schedule_config or {},
        "input_payload": row.input_payload or {},
        "result_payload": row.result_payload or {},
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _task_run_dict(row: BotTaskRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "task_id": row.task_id,
        "profile_key": row.profile_key,
        "trigger_type": row.trigger_type,
        "status": row.status,
        "result_payload": row.result_payload or {},
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
    }


def _approval_dict(row: BotActionApproval) -> dict[str, Any]:
    return {
        "id": row.id,
        "action_id": row.action_id,
        "action_type": row.action_type,
        "title": row.title,
        "profile_key": row.profile_key,
        "status": row.status,
        "payload": row.payload or {},
        "result_payload": row.result_payload or {},
        "requested_by_name": row.requested_by_name,
        "decided_by_name": row.decided_by_name,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _test_case_dict(row: BotTestCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "profile_key": row.profile_key,
        "input_text": row.input_text,
        "conversation_turns": row.conversation_turns or [],
        "expected_skills": row.expected_skills or [],
        "expected_contains": row.expected_contains or [],
        "required_evidence": row.required_evidence,
        "priority": row.priority,
        "last_result": row.last_result or {},
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "status": row.status,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _evaluation_run_dict(row: BotEvaluationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "test_case_id": row.test_case_id,
        "profile_key": row.profile_key,
        "status": row.status,
        "score": row.score,
        "result_payload": row.result_payload or {},
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _intent_correction_dict(row: BotIntentCorrection) -> dict[str, Any]:
    return {
        "id": row.id,
        "phrase": row.phrase,
        "profile_key": row.profile_key,
        "expected_skills": row.expected_skills or [],
        "notes": row.notes,
        "status": row.status,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _collaboration_dict(row: BotCollaborationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "title": row.title,
        "lead_profile_key": row.lead_profile_key,
        "participant_profiles": row.participant_profiles or [],
        "input_text": row.input_text,
        "status": row.status,
        "result_payload": row.result_payload or {},
        "evidence_records": row.evidence_records or [],
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _channel_adapter_dict(row: BotChannelAdapter) -> dict[str, Any]:
    return {
        "id": row.id,
        "adapter_key": row.adapter_key,
        "channel_type": row.channel_type,
        "name": row.name,
        "status": row.status,
        "event_mode": row.event_mode,
        "auth_scheme": row.auth_scheme,
        "signing_required": row.signing_required,
        "rate_limit_per_minute": row.rate_limit_per_minute,
        "retry_policy": row.retry_policy or {},
        "capabilities": row.capabilities or [],
        "config": row.config or {},
        "last_error_message": row.last_error_message,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _inbound_event_dict(row: BotInboundEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "channel_key": row.channel_key,
        "channel_type": row.channel_type,
        "sender_name": row.sender_name,
        "content": row.content,
        "status": row.status,
        "retry_count": row.retry_count,
        "error_message": row.error_message,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


def _inbox_item_dict(row: BotInboxItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "inbox_id": row.inbox_id,
        "conversation_id": row.conversation_id,
        "channel_key": row.channel_key,
        "channel_name": row.channel_name,
        "profile_key": row.profile_key,
        "title": row.title,
        "sender_name": row.sender_name,
        "owner_name": row.owner_name,
        "status": row.status,
        "priority": row.priority,
        "tags": row.tags or [],
        "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
        "handoff_required": row.handoff_required,
        "handoff_reason": row.handoff_reason,
        "resolution_summary": row.resolution_summary,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _handoff_dict(row: BotHandoff) -> dict[str, Any]:
    return {
        "id": row.id,
        "handoff_id": row.handoff_id,
        "inbox_id": row.inbox_id,
        "conversation_id": row.conversation_id,
        "assignee_name": row.assignee_name,
        "status": row.status,
        "reason": row.reason,
        "requested_by_name": row.requested_by_name,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _release_version_dict(row: BotReleaseVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version_id": row.version_id,
        "profile_key": row.profile_key,
        "version": row.version,
        "status": row.status,
        "environment_key": row.environment_key,
        "payload": row.payload or {},
        "test_summary": row.test_summary or {},
        "created_by_name": row.created_by_name,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _feedback_dict(row: BotFeedback) -> dict[str, Any]:
    return {
        "id": row.id,
        "feedback_id": row.feedback_id,
        "conversation_id": row.conversation_id,
        "message_id": row.message_id,
        "profile_key": row.profile_key,
        "rating": row.rating,
        "reason": row.reason,
        "comment": row.comment,
        "status": row.status,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def _knowledge_sync_job_dict(row: BotKnowledgeSyncJob) -> dict[str, Any]:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "name": row.name,
        "source_type": row.source_type,
        "category": row.category,
        "status": row.status,
        "schedule_type": row.schedule_type,
        "source_config": row.source_config or {},
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "result_payload": row.result_payload or {},
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _environment_dict(row: BotEnvironment) -> dict[str, Any]:
    return {
        "id": row.id,
        "environment_key": row.environment_key,
        "name": row.name,
        "status": row.status,
        "is_default": row.is_default,
        "config": row.config or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _compliance_policy_dict(row: BotCompliancePolicy) -> dict[str, Any]:
    return {
        "id": row.id,
        "policy_key": row.policy_key,
        "name": row.name,
        "policy_type": row.policy_type,
        "status": row.status,
        "action": row.action,
        "rules": row.rules or {},
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


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
    import json

    return json.dumps(value, ensure_ascii=False, default=str)[:12000]
