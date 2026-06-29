from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BotAuditLog,
    BotChannelBinding,
    BotCollaborationRun,
    BotSkillRun,
    BotToolCall,
    OperationLog,
)
from ..services.bot_serializers import (
    _approval_dict as _approval_to_dict,
    _conversation_dict as _conversation_to_dict,
    _evaluation_run_dict as _evaluation_run_to_dict,
    _intent_correction_dict as _intent_correction_to_dict,
    _knowledge_file_dict as _knowledge_file_to_dict,
    _message_dict as _message_to_dict,
    _profile_dict as _profile_to_dict,
    _skill_dict as _skill_to_dict,
    _task_dict as _task_to_dict,
    _test_case_dict as _test_case_to_dict,
)


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
