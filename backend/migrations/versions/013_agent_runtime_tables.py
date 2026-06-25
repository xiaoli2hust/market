"""add agent runtime tables.

Revision ID: 013_agent_runtime_tables
Revises: 012_bot_broadcasts
Create Date: 2026-06-25
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "013_agent_runtime_tables"
down_revision = "012_bot_broadcasts"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "bot_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("default_role", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="enabled", nullable=False),
        sa.Column("allowed_skills", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_profiles_status", "bot_profiles", ["status"], schema=SCHEMA)

    op.create_table(
        "bot_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_scenarios", sa.JSON(), nullable=False),
        sa.Column("input_contract", sa.JSON(), nullable=False),
        sa.Column("output_contract", sa.JSON(), nullable=False),
        sa.Column("evidence_rules", sa.JSON(), nullable=False),
        sa.Column("required_permission", sa.String(length=80), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("implementation_status", sa.String(length=30), server_default="implemented", nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_skills_category", "bot_skills", ["category"], schema=SCHEMA)

    op.create_table(
        "bot_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=80), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("simulated_user_role", sa.String(length=80), nullable=True),
        sa.Column("channel_type", sa.String(length=30), server_default="test_console", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_conversations_profile_key", "bot_conversations", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_conversations_channel_type", "bot_conversations", ["channel_type"], schema=SCHEMA)
    op.create_index("ix_bot_conversations_status", "bot_conversations", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_conversations_profile_created", "bot_conversations", ["profile_key", "created_at"], schema=SCHEMA)

    op.create_table(
        "bot_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_pk", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=30), server_default="text", nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_pk"], [f"{SCHEMA}.bot_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_messages_conversation_pk", "bot_messages", ["conversation_pk"], schema=SCHEMA)
    op.create_index("ix_bot_messages_role", "bot_messages", ["role"], schema=SCHEMA)
    op.create_index("ix_bot_messages_created_at", "bot_messages", ["created_at"], schema=SCHEMA)
    op.create_index("ix_bot_messages_conversation_created", "bot_messages", ["conversation_pk", "created_at"], schema=SCHEMA)

    op.create_table(
        "bot_skill_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("conversation_pk", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("skill_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("evidence_records", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_pk"], [f"{SCHEMA}.bot_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], [f"{SCHEMA}.bot_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_skill_runs_conversation_pk", "bot_skill_runs", ["conversation_pk"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_message_id", "bot_skill_runs", ["message_id"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_profile_key", "bot_skill_runs", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_skill_key", "bot_skill_runs", ["skill_key"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_status", "bot_skill_runs", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_skill_created", "bot_skill_runs", ["skill_key", "created_at"], schema=SCHEMA)
    op.create_index("ix_bot_skill_runs_profile_created", "bot_skill_runs", ["profile_key", "created_at"], schema=SCHEMA)

    op.create_table(
        "bot_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_run_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["skill_run_id"], [f"{SCHEMA}.bot_skill_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_tool_calls_skill_run_id", "bot_tool_calls", ["skill_run_id"], schema=SCHEMA)
    op.create_index("ix_bot_tool_calls_tool_name", "bot_tool_calls", ["tool_name"], schema=SCHEMA)
    op.create_index("ix_bot_tool_calls_status", "bot_tool_calls", ["status"], schema=SCHEMA)

    op.create_table(
        "bot_knowledge_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("source_type", sa.String(length=40), server_default="manual_upload", nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="indexed", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_knowledge_files_category", "bot_knowledge_files", ["category"], schema=SCHEMA)
    op.create_index("ix_bot_knowledge_files_status", "bot_knowledge_files", ["status"], schema=SCHEMA)

    op.create_table(
        "bot_knowledge_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_pk", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["file_pk"], [f"{SCHEMA}.bot_knowledge_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_knowledge_chunks_file_pk", "bot_knowledge_chunks", ["file_pk"], schema=SCHEMA)
    op.create_index("ix_bot_knowledge_chunks_file_index", "bot_knowledge_chunks", ["file_pk", "chunk_index"], schema=SCHEMA)

    op.create_table(
        "bot_channel_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_key", sa.String(length=100), nullable=False),
        sa.Column("channel_type", sa.String(length=30), nullable=False),
        sa.Column("channel_name", sa.String(length=120), nullable=False),
        sa.Column("bot_profile_key", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("binding_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_channel_bindings_channel_type", "bot_channel_bindings", ["channel_type"], schema=SCHEMA)
    op.create_index("ix_bot_channel_bindings_bot_profile_key", "bot_channel_bindings", ["bot_profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_channel_bindings_status", "bot_channel_bindings", ["status"], schema=SCHEMA)

    op.create_table(
        "bot_test_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_skills", sa.JSON(), nullable=False),
        sa.Column("expected_contains", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_test_cases_profile_key", "bot_test_cases", ["profile_key"], schema=SCHEMA)

    op.create_table(
        "bot_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=True),
        sa.Column("conversation_id", sa.String(length=80), nullable=True),
        sa.Column("skill_key", sa.String(length=100), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_audit_logs_event_type", "bot_audit_logs", ["event_type"], schema=SCHEMA)
    op.create_index("ix_bot_audit_logs_profile_key", "bot_audit_logs", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_audit_logs_conversation_id", "bot_audit_logs", ["conversation_id"], schema=SCHEMA)
    op.create_index("ix_bot_audit_logs_skill_key", "bot_audit_logs", ["skill_key"], schema=SCHEMA)
    op.create_index("ix_bot_audit_logs_created_at", "bot_audit_logs", ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_bot_audit_logs_created_at", "bot_audit_logs"),
        ("ix_bot_audit_logs_skill_key", "bot_audit_logs"),
        ("ix_bot_audit_logs_conversation_id", "bot_audit_logs"),
        ("ix_bot_audit_logs_profile_key", "bot_audit_logs"),
        ("ix_bot_audit_logs_event_type", "bot_audit_logs"),
        ("ix_bot_test_cases_profile_key", "bot_test_cases"),
        ("ix_bot_channel_bindings_status", "bot_channel_bindings"),
        ("ix_bot_channel_bindings_bot_profile_key", "bot_channel_bindings"),
        ("ix_bot_channel_bindings_channel_type", "bot_channel_bindings"),
        ("ix_bot_knowledge_chunks_file_index", "bot_knowledge_chunks"),
        ("ix_bot_knowledge_chunks_file_pk", "bot_knowledge_chunks"),
        ("ix_bot_knowledge_files_status", "bot_knowledge_files"),
        ("ix_bot_knowledge_files_category", "bot_knowledge_files"),
        ("ix_bot_tool_calls_status", "bot_tool_calls"),
        ("ix_bot_tool_calls_tool_name", "bot_tool_calls"),
        ("ix_bot_tool_calls_skill_run_id", "bot_tool_calls"),
        ("ix_bot_skill_runs_profile_created", "bot_skill_runs"),
        ("ix_bot_skill_runs_skill_created", "bot_skill_runs"),
        ("ix_bot_skill_runs_status", "bot_skill_runs"),
        ("ix_bot_skill_runs_skill_key", "bot_skill_runs"),
        ("ix_bot_skill_runs_profile_key", "bot_skill_runs"),
        ("ix_bot_skill_runs_message_id", "bot_skill_runs"),
        ("ix_bot_skill_runs_conversation_pk", "bot_skill_runs"),
        ("ix_bot_messages_conversation_created", "bot_messages"),
        ("ix_bot_messages_created_at", "bot_messages"),
        ("ix_bot_messages_role", "bot_messages"),
        ("ix_bot_messages_conversation_pk", "bot_messages"),
        ("ix_bot_conversations_profile_created", "bot_conversations"),
        ("ix_bot_conversations_status", "bot_conversations"),
        ("ix_bot_conversations_channel_type", "bot_conversations"),
        ("ix_bot_conversations_profile_key", "bot_conversations"),
        ("ix_bot_skills_category", "bot_skills"),
        ("ix_bot_profiles_status", "bot_profiles"),
    ):
        op.drop_index(index_name, table_name=table_name, schema=SCHEMA)

    for table_name in (
        "bot_audit_logs",
        "bot_test_cases",
        "bot_channel_bindings",
        "bot_knowledge_chunks",
        "bot_knowledge_files",
        "bot_tool_calls",
        "bot_skill_runs",
        "bot_messages",
        "bot_conversations",
        "bot_skills",
        "bot_profiles",
    ):
        op.drop_table(table_name, schema=SCHEMA)
