from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BotChannelAdapter,
    BotChannelBinding,
    BotCompliancePolicy,
    BotEnvironment,
    BotProfile,
    BotSkill,
)

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


def _default_system_prompt(name: str, description: str) -> str:
    return (
        f"你是{name}。{description}\n"
        "回答必须来自受控 Skill、证据记录或明确的用户输入。"
        "不能编造金额、客户状态、时间、风险原因。"
        "涉及外部发送、删除、修改数据等动作时，必须要求确认并写入审计。"
    )



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
