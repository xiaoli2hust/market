from __future__ import annotations

from typing import Any

from ..models import (
    BotActionApproval,
    BotChannelAdapter,
    BotCollaborationRun,
    BotCompliancePolicy,
    BotConversation,
    BotEnvironment,
    BotEvaluationRun,
    BotFeedback,
    BotHandoff,
    BotInboundEvent,
    BotInboxItem,
    BotIntentCorrection,
    BotKnowledgeFile,
    BotKnowledgeSyncJob,
    BotMessage,
    BotProfile,
    BotReleaseVersion,
    BotSkill,
    BotTask,
    BotTaskRun,
    BotTestCase,
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
