"""机器人中心路由。

第一版聚焦一个真实闭环：管理员可以把消息保存为草稿，或发送到管理中心
已配置的钉钉默认群；每次发送都保留状态、结果和操作日志。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import (
    BotAuditLog,
    BotBroadcast,
    BotChannelBinding,
    BotConversation,
    BotKnowledgeFile,
    BotMessage,
    BotProfile,
    BotSkill,
    BotSkillRun,
    BotToolCall,
    OperationLog,
)
from ..services.bot_runtime import (
    ensure_bot_runtime_defaults,
    extract_text_from_html,
    list_bot_runtime_overview,
    run_agent_chat,
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
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """启停或更新 Skill 配置。"""

    await ensure_bot_runtime_defaults(db)
    row = (
        await db.execute(select(BotSkill).where(BotSkill.skill_key == skill_key))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    if "enabled" in payload:
        row.enabled = bool(payload["enabled"])
    if "config" in payload:
        if payload["config"] is not None and not isinstance(payload["config"], dict):
            raise HTTPException(status_code=400, detail="Skill 配置格式不正确")
        row.config = payload["config"] or {}
    _log_operation(db, _user, "bot_skill_update", skill_key, f"enabled={row.enabled}")
    await db.flush()
    await db.refresh(row)
    return _skill_to_dict(row)


@router.post("/chat/test")
async def chat_test(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """对话测试台：模拟真实用户和机器人对话，并记录 Skill 调用链。"""

    try:
        return await run_agent_chat(
            db,
            profile_key=str(payload.get("profile_key") or "management_assistant_agent"),
            conversation_id=payload.get("conversation_id"),
            simulated_user_role=payload.get("simulated_user_role"),
            message=str(payload.get("message") or ""),
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
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
) -> dict[str, Any]:
    """保存一段文本到知识空间并建立切片索引。"""

    try:
        return await upload_knowledge_text(
            db,
            title=str(payload.get("title") or ""),
            text_content=str(payload.get("text_content") or ""),
            category=str(payload.get("category") or "general"),
            user=_user,
            source_type="manual_text",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge/upload")
async def upload_knowledge_file(
    title: str = Form(...),
    category: str = Form("general"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:broadcast")),
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


@router.post("/knowledge/search")
async def search_knowledge(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("bot:view")),
) -> dict[str, Any]:
    """测试知识检索。"""

    query = str(payload.get("query") or "").strip()
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
    payload: dict[str, Any],
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
    payload: dict[str, Any],
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


def _build_broadcast(payload: dict[str, Any], user: dict[str, Any]) -> BotBroadcast:
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="消息标题不能为空")
    if len(title) > _MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息标题不能超过{_MAX_TITLE_LENGTH}字")
    if not content:
        raise HTTPException(status_code=400, detail="消息正文不能为空")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise HTTPException(status_code=400, detail=f"消息正文不能超过{_MAX_CONTENT_LENGTH}字")

    message_type = str(payload.get("message_type") or "markdown").strip().lower()
    if message_type not in _MESSAGE_TYPES:
        raise HTTPException(status_code=400, detail="消息类型不支持")

    target_type = str(payload.get("target_type") or _TARGET_TYPE).strip()
    if target_type != _TARGET_TYPE:
        raise HTTPException(status_code=400, detail="当前版本仅支持发送到管理中心配置的钉钉默认群")

    target_payload = payload.get("target_payload")
    if target_payload is not None and not isinstance(target_payload, dict):
        raise HTTPException(status_code=400, detail="目标配置格式不正确")

    return BotBroadcast(
        title=title,
        content=content,
        message_type=message_type,
        target_type=_TARGET_TYPE,
        target_summary=_TARGET_SUMMARY,
        target_payload=target_payload or {},
        at_all=bool(payload.get("at_all")),
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
