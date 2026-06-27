"""机器人中心路由。

第一版聚焦一个真实闭环：管理员可以把消息保存为草稿，或发送到管理中心
已配置的钉钉默认群；每次发送都保留状态、结果和操作日志。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import (
    BotAuditLog,
    BotActionApproval,
    BotBroadcast,
    BotChannelBinding,
    BotCollaborationRun,
    BotConversation,
    BotEvaluationRun,
    BotIntentCorrection,
    BotKnowledgeFile,
    BotMessage,
    BotProfile,
    BotSkill,
    BotSkillRun,
    BotTask,
    BotTestCase,
    BotToolCall,
    OperationLog,
)
from ..schemas import (
    BotApprovalRequest,
    BotChannelAdapterRequest,
    BotChannelBindingCreateRequest,
    BotChannelBindingUpdateRequest,
    BotChatTestRequest,
    BotCollaborationRequest,
    BotCompliancePolicyRequest,
    BotFeedbackRequest,
    BotHandoffRequest,
    BotInboundTestRequest,
    BotInboxUpdateRequest,
    BotIntentCorrectionRequest,
    BotKnowledgeSearchRequest,
    BotKnowledgeSyncRequest,
    BotKnowledgeTextRequest,
    BotKnowledgeUpdateRequest,
    BotProfileRequest,
    BotReleaseRequest,
    BotSkillUpdateRequest,
    BotTaskRequest,
    BotTestCaseRequest,
    BroadcastRequest,
)
from ..services.bot_runtime import (
    bot_observability_summary,
    create_action_approval,
    create_bot_task,
    create_feedback,
    create_handoff,
    create_intent_correction,
    create_knowledge_sync_job,
    create_release_version,
    create_test_case,
    decide_action_approval,
    ensure_bot_runtime_defaults,
    extract_text_from_html,
    handle_inbound_message,
    list_channel_adapters,
    list_compliance_policies,
    list_environments,
    list_feedback,
    list_handoffs,
    list_inbox_items,
    list_knowledge_sync_jobs,
    list_release_versions,
    list_task_runs,
    list_bot_runtime_overview,
    publish_release_version,
    rollback_release_version,
    run_agent_chat,
    run_bot_task_now,
    run_collaboration,
    run_knowledge_sync_job,
    run_test_case,
    update_inbox_item,
    update_knowledge_metadata,
    upsert_channel_adapter,
    upsert_compliance_policy,
    upsert_bot_profile,
    upload_knowledge_text,
)
from ..services.dingtalk_service import send_markdown, send_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"])

_MESSAGE_TYPES = {"markdown", "text"}
_BROADCAST_STATUSES = {"draft", "sending", "sent", "failed"}
_TARGET_TYPE = "configured_group"
_TARGET_SUMMARY = "当前钉钉默认群（由管理中心配置）"
_MAX_TITLE_LENGTH = 120
_MAX_CONTENT_LENGTH = 5000
_MAX_KNOWLEDGE_FILE_BYTES = 8 * 1024 * 1024


@router.get("/overview")
async def runtime_overview(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """机器人运营中心总览。"""

    return await list_bot_runtime_overview(db)


@router.get("/profiles")
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """机器人 Profile 列表。"""

    await ensure_bot_runtime_defaults(db)
    rows = (
        await db.execute(select(BotProfile).order_by(BotProfile.id.asc()))
    ).scalars().all()
    return [_profile_to_dict(row) for row in rows]


@router.post("/profiles")
async def create_profile(
    payload: BotProfileRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """创建机器人 Profile。"""

    try:
        return await upsert_bot_profile(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/profiles/{profile_key}")
async def update_profile(
    profile_key: str,
    payload: BotProfileRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """更新机器人 Profile 身份、边界和 Skill 绑定。"""

    try:
        return await upsert_bot_profile(db, profile_key=profile_key, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills")
async def list_skills(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """Skill 契约列表。"""

    await ensure_bot_runtime_defaults(db)
    stmt = select(BotSkill).order_by(BotSkill.category.asc(), BotSkill.skill_key.asc())
    if category:
        stmt = stmt.where(BotSkill.category == category.strip())
    rows = (await db.execute(stmt)).scalars().all()
    return [_skill_to_dict(row) for row in rows]


@router.put("/skills/{skill_key}")
async def update_skill(
    skill_key: str,
    payload: BotSkillUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """启停或更新 Skill 配置。"""

    await ensure_bot_runtime_defaults(db)
    row = (
        await db.execute(select(BotSkill).where(BotSkill.skill_key == skill_key))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    data = payload.model_dump(exclude_unset=True)
    if "enabled" in data:
        row.enabled = bool(data["enabled"])
    if "config" in data:
        if data["config"] is not None and not isinstance(data["config"], dict):
            raise HTTPException(status_code=400, detail="Skill 配置格式不正确")
        row.config = data["config"] or {}
    if "trigger_scenarios" in data and isinstance(data["trigger_scenarios"], list):
        row.trigger_scenarios = [str(item).strip()[:120] for item in data["trigger_scenarios"] if str(item).strip()][:20]
    if "evidence_rules" in data and isinstance(data["evidence_rules"], dict):
        row.evidence_rules = data["evidence_rules"]
    if "input_contract" in data and isinstance(data["input_contract"], dict):
        row.input_contract = data["input_contract"]
    if "output_contract" in data and isinstance(data["output_contract"], dict):
        row.output_contract = data["output_contract"]
    _log_operation(db, _user, "bot_skill_update", skill_key, f"enabled={row.enabled}")
    await db.flush()
    await db.refresh(row)
    return _skill_to_dict(row)


@router.post("/chat/test")
async def chat_test(
    payload: BotChatTestRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """对话测试台：模拟真实用户和机器人对话，并记录 Skill 调用链。"""

    try:
        return await run_agent_chat(
            db,
            profile_key=str(payload.profile_key or "management_assistant_agent"),
            conversation_id=payload.conversation_id,
            simulated_user_role=payload.simulated_user_role,
            message=str(payload.message or ""),
            user=_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/conversations")
async def list_conversations(
    profile_key: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """对话列表。"""

    conditions = []
    if profile_key:
        conditions.append(BotConversation.profile_key == profile_key.strip())
    total = (
        await db.execute(select(func.count(BotConversation.id)).where(*conditions))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotConversation)
            .where(*conditions)
            .order_by(BotConversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_conversation_to_dict(row) for row in rows]}


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """对话详情：消息 + Skill 调用链 + 工具调用。"""

    conversation = (
        await db.execute(select(BotConversation).where(BotConversation.conversation_id == conversation_id))
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    messages = (
        await db.execute(
            select(BotMessage)
            .where(BotMessage.conversation_pk == conversation.id)
            .order_by(BotMessage.created_at.asc())
        )
    ).scalars().all()
    runs = (
        await db.execute(
            select(BotSkillRun)
            .where(BotSkillRun.conversation_pk == conversation.id)
            .order_by(BotSkillRun.created_at.asc())
        )
    ).scalars().all()
    run_ids = [row.id for row in runs]
    tool_rows = []
    if run_ids:
        tool_rows = (
            await db.execute(
                select(BotToolCall)
                .where(BotToolCall.skill_run_id.in_(run_ids))
                .order_by(BotToolCall.created_at.asc())
            )
        ).scalars().all()
    tools_by_run: dict[int, list[dict[str, Any]]] = {}
    for tool in tool_rows:
        tools_by_run.setdefault(tool.skill_run_id, []).append(_tool_call_to_dict(tool))
    return {
        "conversation": _conversation_to_dict(conversation),
        "messages": [_message_to_dict(row) for row in messages],
        "skill_runs": [_skill_run_to_dict(row, tools_by_run.get(row.id, [])) for row in runs],
    }


@router.get("/knowledge/files")
async def list_knowledge_files(
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """知识空间文件列表。"""

    conditions = []
    if category:
        conditions.append(BotKnowledgeFile.category == category.strip())
    total = (
        await db.execute(select(func.count(BotKnowledgeFile.id)).where(*conditions))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotKnowledgeFile)
            .where(*conditions)
            .order_by(BotKnowledgeFile.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_knowledge_file_to_dict(row) for row in rows]}


@router.post("/knowledge/text")
async def create_knowledge_text(
    payload: BotKnowledgeTextRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:knowledge")),
) -> dict[str, Any]:
    """保存一段文本到知识空间并建立切片索引。"""

    try:
        return await upload_knowledge_text(
            db,
            title=str(payload.title or ""),
            text_content=str(payload.text_content or ""),
            category=str(payload.category or "general"),
            user=_user,
            source_type="manual_text",
            owner_profile_key=payload.owner_profile_key,
            visibility_scope=str(payload.visibility_scope or "all_bots"),
            tags=payload.tags if isinstance(payload.tags, list) else [],
            review_status=str(payload.review_status or "approved"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge/upload")
async def upload_knowledge_file(
    title: str = Form(...),
    category: str = Form("general"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:knowledge")),
) -> dict[str, Any]:
    """上传 HTML/TXT/Markdown 文件到知识空间。"""

    raw = await file.read()
    if len(raw) > _MAX_KNOWLEDGE_FILE_BYTES:
        raise HTTPException(status_code=400, detail="知识文件不能超过 8MB")
    lower_name = (file.filename or "").lower()
    if not lower_name.endswith((".html", ".htm", ".txt", ".md")):
        raise HTTPException(status_code=400, detail="当前支持 HTML、TXT、Markdown 文件")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gb18030", errors="ignore")
    if lower_name.endswith((".html", ".htm")):
        text = extract_text_from_html(text)
    try:
        return await upload_knowledge_text(
            db,
            title=title,
            text_content=text,
            category=category,
            user=_user,
            file_name=file.filename,
            content_type=file.content_type,
            source_type="manual_upload",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/knowledge/files/{file_id}")
async def update_knowledge_file(
    file_id: str,
    payload: BotKnowledgeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:knowledge")),
) -> dict[str, Any]:
    """更新知识生命周期状态、可见范围和标签。"""

    try:
        return await update_knowledge_metadata(db, file_id=file_id, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.post("/knowledge/search")
async def search_knowledge(
    payload: BotKnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """测试知识检索。"""

    query = str(payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="检索问题不能为空")
    result = await run_agent_chat(
        db,
        profile_key="management_assistant_agent",
        message=f"请检索知识空间：{query}",
        user=_user,
        simulated_user_role="知识检索测试",
    )
    return {
        "query": query,
        "evidence_records": [
            item for item in result.get("evidence_records", [])
            if item.get("source_type") in {"knowledge_file", "department_weekly_report"}
        ],
        "conversation": result.get("conversation"),
    }


@router.post("/inbound/test")
async def inbound_test(
    payload: BotInboundTestRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """模拟真实群聊入站消息，用于验证钉钉接入后的机器人回答链路。"""

    try:
        return await handle_inbound_message(
            db,
            channel_key=str(payload.channel_key or "dingtalk_default"),
            content=str(payload.content or ""),
            sender_id=str(payload.sender_id or _user_id(_user) or "local_tester"),
            sender_name=str(payload.sender_name or _user_name(_user)),
            raw_payload={"source": "manual_inbound_test"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/channel-adapters")
async def channel_adapters(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """外部群聊渠道适配器。"""

    return await list_channel_adapters(db)


@router.post("/channel-adapters")
async def save_channel_adapter(
    payload: BotChannelAdapterRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """新增或更新渠道适配器、认证和限流策略。"""

    try:
        return await upsert_channel_adapter(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/channel-bindings")
async def list_channel_bindings(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """群聊接入绑定。"""

    await ensure_bot_runtime_defaults(db)
    rows = (
        await db.execute(select(BotChannelBinding).order_by(BotChannelBinding.created_at.desc()))
    ).scalars().all()
    return [_channel_binding_to_dict(row) for row in rows]


@router.post("/channel-bindings")
async def create_channel_binding(
    payload: BotChannelBindingCreateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """新增外部群聊与机器人绑定。"""

    await ensure_bot_runtime_defaults(db)
    channel_key = str(payload.channel_key or "").strip()
    if not channel_key:
        channel_key = f"channel_{uuid.uuid4().hex[:8]}"
    if (
        await db.execute(select(BotChannelBinding).where(BotChannelBinding.channel_key == channel_key))
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="群聊标识已存在")
    row = BotChannelBinding(
        channel_key=channel_key[:100],
        channel_type=str(payload.channel_type or "dingtalk")[:30],
        channel_name=str(payload.channel_name or "未命名群聊")[:120],
        bot_profile_key=str(payload.bot_profile_key or "management_assistant_agent")[:80],
        external_id=str(payload.external_id or "")[:255] or None,
        binding_config=payload.binding_config if isinstance(payload.binding_config, dict) else {},
        status=str(payload.status or "active")[:20],
    )
    db.add(row)
    _log_operation(db, _user, "bot_channel_binding_create", row.channel_key, row.channel_name)
    await db.flush()
    await db.refresh(row)
    return _channel_binding_to_dict(row)


@router.put("/channel-bindings/{channel_key}")
async def update_channel_binding(
    channel_key: str,
    payload: BotChannelBindingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """更新群聊绑定状态或机器人 Profile。"""

    row = (
        await db.execute(select(BotChannelBinding).where(BotChannelBinding.channel_key == channel_key))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="群聊绑定不存在")
    data = payload.model_dump(exclude_unset=True)
    for field, limit in {"channel_name": 120, "channel_type": 30, "bot_profile_key": 80, "external_id": 255, "status": 20}.items():
        if field in data:
            value = str(data.get(field) or "").strip()
            setattr(row, field, value[:limit] if value else None if field == "external_id" else getattr(row, field))
    if "binding_config" in data and isinstance(data["binding_config"], dict):
        row.binding_config = data["binding_config"]
    row.updated_at = datetime.now(timezone.utc)
    _log_operation(db, _user, "bot_channel_binding_update", row.channel_key, row.status)
    await db.flush()
    await db.refresh(row)
    return _channel_binding_to_dict(row)


@router.get("/inbox")
async def bot_inbox(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """机器人生产收件箱：所有入站消息和需要人工处理的事项。"""

    return await list_inbox_items(db, status=status)


@router.put("/inbox/{inbox_id}")
async def save_inbox_item(
    inbox_id: str,
    payload: BotInboxUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:approve")),
) -> dict[str, Any]:
    """更新收件箱状态、负责人、优先级或处理结论。"""

    try:
        return await update_inbox_item(db, inbox_id=inbox_id, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.post("/inbox/{inbox_id}/handoff")
async def handoff_inbox_item(
    inbox_id: str,
    payload: BotHandoffRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:approve")),
) -> dict[str, Any]:
    """把机器人无法直接闭环的事项转给人工负责人。"""

    try:
        return await create_handoff(db, inbox_id=inbox_id, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.get("/handoffs")
async def bot_handoffs(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """人工接管记录。"""

    return await list_handoffs(db, status=status)


@router.get("/skill-runs")
async def list_skill_runs(
    skill_key: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """Skill 运行日志。"""

    conditions = []
    if skill_key:
        conditions.append(BotSkillRun.skill_key == skill_key.strip())
    total = (
        await db.execute(select(func.count(BotSkillRun.id)).where(*conditions))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotSkillRun)
            .where(*conditions)
            .order_by(BotSkillRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_skill_run_to_dict(row, []) for row in rows]}


@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """机器人审计日志。"""

    total = (await db.execute(select(func.count(BotAuditLog.id)))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotAuditLog)
            .order_by(BotAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_audit_log_to_dict(row) for row in rows]}


@router.get("/tasks")
async def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    total = (await db.execute(select(func.count(BotTask.id)))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotTask).order_by(BotTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_task_to_dict(row) for row in rows]}


@router.post("/tasks")
async def create_task(
    payload: BotTaskRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    try:
        return await create_bot_task(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    try:
        return await run_bot_task_now(db, task_id=task_id, user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.get("/task-runs")
async def bot_task_runs(
    task_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """自动任务运行历史。"""

    return await list_task_runs(db, task_id=task_id)


@router.get("/approvals")
async def list_approvals(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    conditions = []
    if status:
        conditions.append(BotActionApproval.status == status.strip())
    total = (await db.execute(select(func.count(BotActionApproval.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotActionApproval)
            .where(*conditions)
            .order_by(BotActionApproval.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_approval_to_dict(row) for row in rows]}


@router.post("/approvals")
async def create_approval(
    payload: BotApprovalRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:approve")),
) -> dict[str, Any]:
    try:
        return await create_action_approval(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approvals/{action_id}/{decision}")
async def decide_approval(
    action_id: str,
    decision: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:approve")),
) -> dict[str, Any]:
    try:
        return await decide_action_approval(db, action_id=action_id, decision=decision, user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/test-cases")
async def list_test_cases(
    profile_key: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    conditions = []
    if profile_key:
        conditions.append(BotTestCase.profile_key == profile_key.strip())
    total = (await db.execute(select(func.count(BotTestCase.id)).where(*conditions))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotTestCase)
            .where(*conditions)
            .order_by(BotTestCase.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_test_case_to_dict(row) for row in rows]}


@router.post("/test-cases")
async def create_case(
    payload: BotTestCaseRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    try:
        return await create_test_case(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test-cases/{case_id}/run")
async def run_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    try:
        return await run_test_case(db, case_id=case_id, user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.get("/evaluation-runs")
async def list_evaluation_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    total = (await db.execute(select(func.count(BotEvaluationRun.id)))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotEvaluationRun)
            .order_by(BotEvaluationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_evaluation_run_to_dict(row) for row in rows]}


@router.get("/intent-corrections")
async def list_intent_corrections(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(BotIntentCorrection).order_by(BotIntentCorrection.created_at.desc()).limit(50))
    ).scalars().all()
    return [_intent_correction_to_dict(row) for row in rows]


@router.post("/intent-corrections")
async def create_correction(
    payload: BotIntentCorrectionRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    try:
        return await create_intent_correction(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/collaborations")
async def list_collaborations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    total = (await db.execute(select(func.count(BotCollaborationRun.id)))).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotCollaborationRun)
            .order_by(BotCollaborationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_collaboration_to_dict(row) for row in rows]}


@router.post("/collaborations/run")
async def create_collaboration(
    payload: BotCollaborationRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    try:
        return await run_collaboration(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/releases")
async def bot_releases(
    profile_key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """机器人发布版本。"""

    return await list_release_versions(db, profile_key=profile_key)


@router.post("/releases")
async def create_release(
    payload: BotReleaseRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """把当前机器人配置快照保存为待发布版本。"""

    try:
        return await create_release_version(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/releases/{version_id}/publish")
async def publish_release(
    version_id: str,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    """发布版本；默认会先跑评测门禁。"""

    try:
        return await publish_release_version(db, version_id=version_id, user=_user, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/releases/{version_id}/rollback")
async def rollback_release(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """把版本标记为已回滚，保留发布审计。"""

    try:
        return await rollback_release_version(db, version_id=version_id, user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.get("/feedback")
async def bot_feedback(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """用户反馈与质量问题队列。"""

    return await list_feedback(db, status=status)


@router.post("/feedback")
async def save_feedback(
    payload: BotFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:evaluate")),
) -> dict[str, Any]:
    """记录一次机器人回答反馈。"""

    try:
        return await create_feedback(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge-sync")
async def knowledge_sync_jobs(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """知识同步任务。"""

    return await list_knowledge_sync_jobs(db)


@router.post("/knowledge-sync")
async def create_knowledge_sync(
    payload: BotKnowledgeSyncRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:knowledge")),
) -> dict[str, Any]:
    """创建知识同步任务。"""

    try:
        return await create_knowledge_sync_job(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge-sync/{job_id}/run")
async def run_knowledge_sync(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:knowledge")),
) -> dict[str, Any]:
    """立即运行知识同步任务。"""

    try:
        return await run_knowledge_sync_job(db, job_id=job_id, user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc


@router.get("/environments")
async def bot_environments(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """机器人运行环境。"""

    return await list_environments(db)


@router.get("/compliance-policies")
async def compliance_policies(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> list[dict[str, Any]]:
    """机器人内容安全与留存策略。"""

    return await list_compliance_policies(db)


@router.post("/compliance-policies")
async def save_compliance_policy(
    payload: BotCompliancePolicyRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:configure")),
) -> dict[str, Any]:
    """新增或更新机器人合规策略。"""

    try:
        return await upsert_compliance_policy(db, payload=payload.model_dump(exclude_unset=True), user=_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/observability-summary")
async def observability_summary(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """机器人近 7 天运行健康度。"""

    return await bot_observability_summary(db)


@router.get("/quality-summary")
async def quality_summary(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    total_cases = (await db.execute(select(func.count(BotTestCase.id)))).scalar_one() or 0
    failed_runs = (await db.execute(select(func.count(BotEvaluationRun.id)).where(BotEvaluationRun.status == "failed"))).scalar_one() or 0
    pending_actions = (await db.execute(select(func.count(BotActionApproval.id)).where(BotActionApproval.status == "pending"))).scalar_one() or 0
    no_evidence_runs = (
        await db.execute(select(func.count(BotSkillRun.id)).where(func.json_array_length(BotSkillRun.evidence_records) == 0))
    ).scalar_one() or 0
    return {
        "test_cases": int(total_cases),
        "failed_evaluation_runs": int(failed_runs),
        "pending_actions": int(pending_actions),
        "no_evidence_skill_runs": int(no_evidence_runs),
    }


@router.get("/broadcasts")
async def list_broadcasts(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """查看机器人群发记录。"""

    conditions = []
    if status:
        clean_status = status.strip()
        if clean_status not in _BROADCAST_STATUSES:
            raise HTTPException(status_code=400, detail="群发状态不支持")
        conditions.append(BotBroadcast.status == clean_status)

    total = (
        await db.execute(select(func.count(BotBroadcast.id)).where(*conditions))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            select(BotBroadcast)
            .where(*conditions)
            .order_by(BotBroadcast.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"total": int(total), "items": [_broadcast_to_dict(row) for row in rows]}


@router.post("/broadcasts")
async def create_broadcast(
    payload: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """保存群发草稿。"""

    record = _build_broadcast(payload, _user)
    db.add(record)
    await db.flush()
    _log_operation(db, _user, "bot_broadcast_create", f"broadcast:{record.id}", record.title)
    await db.refresh(record)
    return _broadcast_to_dict(record)


@router.post("/broadcasts/send")
async def create_and_send_broadcast(
    payload: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """创建群发记录并立即发送。"""

    record = _build_broadcast(payload, _user)
    db.add(record)
    await db.flush()
    _log_operation(db, _user, "bot_broadcast_create", f"broadcast:{record.id}", record.title)
    return await _send_broadcast(db, record, _user)


@router.post("/broadcasts/{broadcast_id}/send")
async def send_existing_broadcast(
    broadcast_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """发送已有草稿或失败记录。"""

    record = (
        await db.execute(select(BotBroadcast).where(BotBroadcast.id == broadcast_id))
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="群发记录不存在")
    if record.status not in {"draft", "failed"}:
        raise HTTPException(status_code=400, detail="该记录当前状态不能重复发送")
    return await _send_broadcast(db, record, _user)


def _build_broadcast(payload: BroadcastRequest, user: dict[str, Any]) -> BotBroadcast:
    title = str(payload.title or "").strip()
    content = str(payload.content or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="消息标题不能为空")
    if len(title) > _MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息标题不能超过{_MAX_TITLE_LENGTH}字")
    if not content:
        raise HTTPException(status_code=400, detail="消息正文不能为空")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息正文不能超过{_MAX_CONTENT_LENGTH}字")

    message_type = str(payload.message_type or "markdown").strip().lower()
    if message_type not in _MESSAGE_TYPES:
        raise HTTPException(status_code=400, detail="消息类型不支持")

    target_type = str(payload.target_type or _TARGET_TYPE).strip()
    if target_type != _TARGET_TYPE:
        raise HTTPException(status_code=400, detail="当前版本仅支持发送到管理中心配置的钉钉默认群")

    target_payload = payload.target_payload
    if target_payload is not None and not isinstance(target_payload, dict):
        raise HTTPException(status_code=400, detail="目标配置格式不正确")

    return BotBroadcast(
        title=title,
        content=content,
        message_type=message_type,
        target_type=_TARGET_TYPE,
        target_summary=_TARGET_SUMMARY,
        target_payload=target_payload or {},
        at_all=bool(payload.at_all),
        status="draft",
        created_by=_user_id(user),
        created_by_name=_user_name(user),
    )


async def _send_broadcast(
    db: AsyncSession,
    record: BotBroadcast,
    user: dict[str, Any],
) -> dict[str, Any]:
    record.status = "sending"
    record.error_message = None
    record.result_message = None
    record.result_payload = None
    await db.flush()

    try:
        if record.message_type == "text":
            result = await send_text(db, record.content, is_at_all=record.at_all)
        else:
            result = await send_markdown(
                db,
                record.title,
                _markdown_text(record.title, record.content),
                is_at_all=record.at_all,
            )
    except Exception:
        logger.exception("bot broadcast send failed")
        result = {"success": False, "message": "机器人发送失败，请检查钉钉配置或稍后重试", "raw": {}}

    now = datetime.now(timezone.utc)
    record.sent_by = _user_id(user)
    record.sent_by_name = _user_name(user)
    record.sent_at = now
    record.result_message = str(result.get("message") or "")
    record.result_payload = result.get("raw") if isinstance(result.get("raw"), dict) else {}
    if result.get("success"):
        record.status = "sent"
        record.error_message = None
    else:
        record.status = "failed"
        record.error_message = record.result_message or "机器人发送失败"

    await db.flush()
    _log_operation(
        db,
        user,
        "bot_broadcast_send",
        f"broadcast:{record.id}",
        f"{record.status}:{record.result_message or record.title}",
    )
    await db.refresh(record)
    return _broadcast_to_dict(record)


def _markdown_text(title: str, content: str) -> str:
    clean = content.strip()
    if clean.startswith("#"):
        return clean
    return f"## {title.strip()}\n\n{clean}"


def _broadcast_to_dict(row: BotBroadcast) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "message_type": row.message_type,
        "target_type": row.target_type,
        "target_summary": row.target_summary,
        "target_payload": row.target_payload or {},
        "at_all": row.at_all,
        "status": row.status,
        "created_by": row.created_by,
        "created_by_name": row.created_by_name,
        "sent_by": row.sent_by,
        "sent_by_name": row.sent_by_name,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "result_message": row.result_message,
        "result_payload": row.result_payload or {},
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _profile_to_dict(row: BotProfile) -> dict[str, Any]:
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


def _skill_to_dict(row: BotSkill) -> dict[str, Any]:
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


def _conversation_to_dict(row: BotConversation) -> dict[str, Any]:
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


def _message_to_dict(row: BotMessage) -> dict[str, Any]:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "content_type": row.content_type,
        "source": row.source,
        "meta": row.meta or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _knowledge_file_to_dict(row: BotKnowledgeFile) -> dict[str, Any]:
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


def _channel_binding_to_dict(row: BotChannelBinding) -> dict[str, Any]:
    return {
        "id": row.id,
        "channel_key": row.channel_key,
        "channel_type": row.channel_type,
        "channel_name": row.channel_name,
        "bot_profile_key": row.bot_profile_key,
        "external_id": row.external_id,
        "binding_config": row.binding_config or {},
        "status": row.status,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _skill_run_to_dict(row: BotSkillRun, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "conversation_pk": row.conversation_pk,
        "message_id": row.message_id,
        "profile_key": row.profile_key,
        "skill_key": row.skill_key,
        "status": row.status,
        "input_payload": row.input_payload or {},
        "output_payload": row.output_payload or {},
        "evidence_records": row.evidence_records or [],
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "tool_calls": tool_calls,
    }


def _tool_call_to_dict(row: BotToolCall) -> dict[str, Any]:
    return {
        "id": row.id,
        "skill_run_id": row.skill_run_id,
        "tool_name": row.tool_name,
        "status": row.status,
        "input_payload": row.input_payload or {},
        "output_payload": row.output_payload or {},
        "duration_ms": row.duration_ms,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _audit_log_to_dict(row: BotAuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "profile_key": row.profile_key,
        "conversation_id": row.conversation_id,
        "skill_key": row.skill_key,
        "actor_name": row.actor_name,
        "payload": row.payload or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _task_to_dict(row: BotTask) -> dict[str, Any]:
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


def _approval_to_dict(row: BotActionApproval) -> dict[str, Any]:
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


def _test_case_to_dict(row: BotTestCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "profile_key": row.profile_key,
        "input_text": row.input_text,
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


def _evaluation_run_to_dict(row: BotEvaluationRun) -> dict[str, Any]:
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


def _intent_correction_to_dict(row: BotIntentCorrection) -> dict[str, Any]:
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


def _collaboration_to_dict(row: BotCollaborationRun) -> dict[str, Any]:
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


def _user_id(user: dict[str, Any]) -> int | None:
    value = user.get("id")
    return int(value) if isinstance(value, int) or str(value or "").isdigit() else None


def _user_name(user: dict[str, Any]) -> str:
    return str(user.get("display_name") or user.get("username") or user.get("sub") or "系统用户")


def _log_operation(
    db: AsyncSession,
    user: dict[str, Any],
    action: str,
    target: str,
    detail: str,
) -> None:
    db.add(
        OperationLog(
            user_id=_user_id(user),
            username=_user_name(user),
            action=action,
            target=target,
            detail=detail[:1000],
        )
    )
