"""add enterprise bot operations tables.

Revision ID: 015_bot_enterprise_operations
Revises: 014_bot_operations_upgrade
Create Date: 2026-06-25
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "015_bot_enterprise_operations"
down_revision = "014_bot_operations_upgrade"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column(
        "bot_test_cases",
        sa.Column("conversation_turns", sa.JSON(), server_default="[]", nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        "bot_channel_adapters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("adapter_key", sa.String(length=80), nullable=False),
        sa.Column("channel_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="enabled", nullable=False),
        sa.Column("event_mode", sa.String(length=40), server_default="webhook", nullable=False),
        sa.Column("auth_scheme", sa.String(length=40), server_default="signed_webhook", nullable=False),
        sa.Column("signing_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), server_default="60", nullable=False),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adapter_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_channel_adapters_adapter_key", "bot_channel_adapters", ["adapter_key"], schema=SCHEMA)
    op.create_index("ix_bot_channel_adapters_channel_type", "bot_channel_adapters", ["channel_type"], schema=SCHEMA)
    op.create_index("ix_bot_channel_adapters_status", "bot_channel_adapters", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_channel_adapters_created_at", "bot_channel_adapters", ["created_at"], schema=SCHEMA)
    op.create_index("ix_bot_channel_adapters_type_status", "bot_channel_adapters", ["channel_type", "status"], schema=SCHEMA)

    op.create_table(
        "bot_inbound_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("dedup_key", sa.String(length=160), nullable=False),
        sa.Column("channel_key", sa.String(length=100), nullable=False),
        sa.Column("channel_type", sa.String(length=40), nullable=False),
        sa.Column("sender_id", sa.String(length=120), nullable=True),
        sa.Column("sender_name", sa.String(length=120), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("dedup_key"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_inbound_events_channel_key": ["channel_key"],
        "ix_bot_inbound_events_channel_type": ["channel_type"],
        "ix_bot_inbound_events_sender_id": ["sender_id"],
        "ix_bot_inbound_events_status": ["status"],
        "ix_bot_inbound_events_received_at": ["received_at"],
        "ix_bot_inbound_events_channel_received": ["channel_key", "received_at"],
        "ix_bot_inbound_events_status_received": ["status", "received_at"],
    }.items():
        op.create_index(index_name, "bot_inbound_events", columns, schema=SCHEMA)

    op.create_table(
        "bot_inbox_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inbox_id", sa.String(length=80), nullable=False),
        sa.Column("conversation_id", sa.String(length=80), nullable=False),
        sa.Column("channel_key", sa.String(length=100), nullable=False),
        sa.Column("channel_name", sa.String(length=120), nullable=True),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sender_name", sa.String(length=120), nullable=True),
        sa.Column("owner_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="P2", nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("handoff_reason", sa.Text(), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inbox_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_inbox_items_conversation_id": ["conversation_id"],
        "ix_bot_inbox_items_channel_key": ["channel_key"],
        "ix_bot_inbox_items_profile_key": ["profile_key"],
        "ix_bot_inbox_items_status": ["status"],
        "ix_bot_inbox_items_priority": ["priority"],
        "ix_bot_inbox_items_last_message_at": ["last_message_at"],
        "ix_bot_inbox_items_created_at": ["created_at"],
        "ix_bot_inbox_items_status_priority": ["status", "priority"],
        "ix_bot_inbox_items_channel_status": ["channel_key", "status"],
    }.items():
        op.create_index(index_name, "bot_inbox_items", columns, schema=SCHEMA)

    op.create_table(
        "bot_handoffs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("handoff_id", sa.String(length=80), nullable=False),
        sa.Column("inbox_id", sa.String(length=80), nullable=False),
        sa.Column("conversation_id", sa.String(length=80), nullable=False),
        sa.Column("assignee_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_by_name", sa.String(length=120), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handoff_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_handoffs_inbox_id": ["inbox_id"],
        "ix_bot_handoffs_conversation_id": ["conversation_id"],
        "ix_bot_handoffs_status": ["status"],
        "ix_bot_handoffs_created_at": ["created_at"],
    }.items():
        op.create_index(index_name, "bot_handoffs", columns, schema=SCHEMA)

    op.create_table(
        "bot_task_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_task_runs_task_id": ["task_id"],
        "ix_bot_task_runs_profile_key": ["profile_key"],
        "ix_bot_task_runs_status": ["status"],
        "ix_bot_task_runs_started_at": ["started_at"],
        "ix_bot_task_runs_task_started": ["task_id", "started_at"],
        "ix_bot_task_runs_status_started": ["status", "started_at"],
    }.items():
        op.create_index(index_name, "bot_task_runs", columns, schema=SCHEMA)

    op.create_table(
        "bot_release_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.String(length=80), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("environment_key", sa.String(length=40), server_default="prod", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("test_summary", sa.JSON(), nullable=True),
        sa.Column("created_by_name", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_release_versions_profile_key": ["profile_key"],
        "ix_bot_release_versions_status": ["status"],
        "ix_bot_release_versions_environment_key": ["environment_key"],
        "ix_bot_release_versions_created_at": ["created_at"],
        "ix_bot_release_versions_profile_version": ["profile_key", "version"],
        "ix_bot_release_versions_env_status": ["environment_key", "status"],
    }.items():
        op.create_index(index_name, "bot_release_versions", columns, schema=SCHEMA)

    op.create_table(
        "bot_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_id", sa.String(length=80), nullable=False),
        sa.Column("conversation_id", sa.String(length=80), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("profile_key", sa.String(length=80), nullable=True),
        sa.Column("rating", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("created_by_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feedback_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_feedback_conversation_id": ["conversation_id"],
        "ix_bot_feedback_message_id": ["message_id"],
        "ix_bot_feedback_profile_key": ["profile_key"],
        "ix_bot_feedback_rating": ["rating"],
        "ix_bot_feedback_status": ["status"],
        "ix_bot_feedback_created_at": ["created_at"],
    }.items():
        op.create_index(index_name, "bot_feedback", columns, schema=SCHEMA)

    op.create_table(
        "bot_knowledge_sync_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="enabled", nullable=False),
        sa.Column("schedule_type", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("source_config", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("created_by_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_knowledge_sync_jobs_source_type": ["source_type"],
        "ix_bot_knowledge_sync_jobs_category": ["category"],
        "ix_bot_knowledge_sync_jobs_status": ["status"],
        "ix_bot_knowledge_sync_jobs_created_at": ["created_at"],
    }.items():
        op.create_index(index_name, "bot_knowledge_sync_jobs", columns, schema=SCHEMA)

    op.create_table(
        "bot_environments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("environment_key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="enabled", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("environment_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_environments_environment_key", "bot_environments", ["environment_key"], schema=SCHEMA)
    op.create_index("ix_bot_environments_status", "bot_environments", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_environments_created_at", "bot_environments", ["created_at"], schema=SCHEMA)

    op.create_table(
        "bot_compliance_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("policy_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="enabled", nullable=False),
        sa.Column("action", sa.String(length=40), server_default="warn", nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_by_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_key"),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_bot_compliance_policies_policy_type": ["policy_type"],
        "ix_bot_compliance_policies_status": ["status"],
        "ix_bot_compliance_policies_created_at": ["created_at"],
    }.items():
        op.create_index(index_name, "bot_compliance_policies", columns, schema=SCHEMA)


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_bot_compliance_policies_created_at", "bot_compliance_policies"),
        ("ix_bot_compliance_policies_status", "bot_compliance_policies"),
        ("ix_bot_compliance_policies_policy_type", "bot_compliance_policies"),
        ("ix_bot_environments_created_at", "bot_environments"),
        ("ix_bot_environments_status", "bot_environments"),
        ("ix_bot_environments_environment_key", "bot_environments"),
        ("ix_bot_knowledge_sync_jobs_created_at", "bot_knowledge_sync_jobs"),
        ("ix_bot_knowledge_sync_jobs_status", "bot_knowledge_sync_jobs"),
        ("ix_bot_knowledge_sync_jobs_category", "bot_knowledge_sync_jobs"),
        ("ix_bot_knowledge_sync_jobs_source_type", "bot_knowledge_sync_jobs"),
        ("ix_bot_feedback_created_at", "bot_feedback"),
        ("ix_bot_feedback_status", "bot_feedback"),
        ("ix_bot_feedback_rating", "bot_feedback"),
        ("ix_bot_feedback_profile_key", "bot_feedback"),
        ("ix_bot_feedback_message_id", "bot_feedback"),
        ("ix_bot_feedback_conversation_id", "bot_feedback"),
        ("ix_bot_release_versions_env_status", "bot_release_versions"),
        ("ix_bot_release_versions_profile_version", "bot_release_versions"),
        ("ix_bot_release_versions_created_at", "bot_release_versions"),
        ("ix_bot_release_versions_environment_key", "bot_release_versions"),
        ("ix_bot_release_versions_status", "bot_release_versions"),
        ("ix_bot_release_versions_profile_key", "bot_release_versions"),
        ("ix_bot_task_runs_status_started", "bot_task_runs"),
        ("ix_bot_task_runs_task_started", "bot_task_runs"),
        ("ix_bot_task_runs_started_at", "bot_task_runs"),
        ("ix_bot_task_runs_status", "bot_task_runs"),
        ("ix_bot_task_runs_profile_key", "bot_task_runs"),
        ("ix_bot_task_runs_task_id", "bot_task_runs"),
        ("ix_bot_handoffs_created_at", "bot_handoffs"),
        ("ix_bot_handoffs_status", "bot_handoffs"),
        ("ix_bot_handoffs_conversation_id", "bot_handoffs"),
        ("ix_bot_handoffs_inbox_id", "bot_handoffs"),
        ("ix_bot_inbox_items_channel_status", "bot_inbox_items"),
        ("ix_bot_inbox_items_status_priority", "bot_inbox_items"),
        ("ix_bot_inbox_items_created_at", "bot_inbox_items"),
        ("ix_bot_inbox_items_last_message_at", "bot_inbox_items"),
        ("ix_bot_inbox_items_priority", "bot_inbox_items"),
        ("ix_bot_inbox_items_status", "bot_inbox_items"),
        ("ix_bot_inbox_items_profile_key", "bot_inbox_items"),
        ("ix_bot_inbox_items_channel_key", "bot_inbox_items"),
        ("ix_bot_inbox_items_conversation_id", "bot_inbox_items"),
        ("ix_bot_inbound_events_status_received", "bot_inbound_events"),
        ("ix_bot_inbound_events_channel_received", "bot_inbound_events"),
        ("ix_bot_inbound_events_received_at", "bot_inbound_events"),
        ("ix_bot_inbound_events_status", "bot_inbound_events"),
        ("ix_bot_inbound_events_sender_id", "bot_inbound_events"),
        ("ix_bot_inbound_events_channel_type", "bot_inbound_events"),
        ("ix_bot_inbound_events_channel_key", "bot_inbound_events"),
        ("ix_bot_channel_adapters_type_status", "bot_channel_adapters"),
        ("ix_bot_channel_adapters_created_at", "bot_channel_adapters"),
        ("ix_bot_channel_adapters_status", "bot_channel_adapters"),
        ("ix_bot_channel_adapters_channel_type", "bot_channel_adapters"),
        ("ix_bot_channel_adapters_adapter_key", "bot_channel_adapters"),
    ):
        op.drop_index(index_name, table_name=table_name, schema=SCHEMA)
    for table_name in (
        "bot_compliance_policies",
        "bot_environments",
        "bot_knowledge_sync_jobs",
        "bot_feedback",
        "bot_release_versions",
        "bot_task_runs",
        "bot_handoffs",
        "bot_inbox_items",
        "bot_inbound_events",
        "bot_channel_adapters",
    ):
        op.drop_table(table_name, schema=SCHEMA)
    op.drop_column("bot_test_cases", "conversation_turns", schema=SCHEMA)
