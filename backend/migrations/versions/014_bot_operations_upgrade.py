"""upgrade bot operations runtime.

Revision ID: 014_bot_operations_upgrade
Revises: 013_agent_runtime_tables
Create Date: 2026-06-25
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "014_bot_operations_upgrade"
down_revision = "013_agent_runtime_tables"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    for column in (
        sa.Column("review_status", sa.String(length=20), server_default="approved", nullable=False),
        sa.Column("visibility_scope", sa.String(length=40), server_default="all_bots", nullable=False),
        sa.Column("owner_profile_key", sa.String(length=80), nullable=True),
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("bot_knowledge_files", column, schema=SCHEMA)
    op.create_index("ix_bot_knowledge_files_review_status", "bot_knowledge_files", ["review_status"], schema=SCHEMA)
    op.create_index("ix_bot_knowledge_files_visibility_scope", "bot_knowledge_files", ["visibility_scope"], schema=SCHEMA)
    op.create_index("ix_bot_knowledge_files_owner_profile_key", "bot_knowledge_files", ["owner_profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_knowledge_files_expires_at", "bot_knowledge_files", ["expires_at"], schema=SCHEMA)

    for column in (
        sa.Column("required_evidence", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="P1", nullable=False),
        sa.Column("last_result", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("bot_test_cases", column, schema=SCHEMA)
    op.create_index("ix_bot_test_cases_priority", "bot_test_cases", ["priority"], schema=SCHEMA)

    op.create_table(
        "bot_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="enabled", nullable=False),
        sa.Column("schedule_type", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("schedule_config", sa.JSON(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_tasks_task_type", "bot_tasks", ["task_type"], schema=SCHEMA)
    op.create_index("ix_bot_tasks_profile_key", "bot_tasks", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_tasks_status", "bot_tasks", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_tasks_created_at", "bot_tasks", ["created_at"], schema=SCHEMA)
    op.create_index("ix_bot_tasks_profile_status", "bot_tasks", ["profile_key", "status"], schema=SCHEMA)
    op.create_index("ix_bot_tasks_type_status", "bot_tasks", ["task_type", "status"], schema=SCHEMA)

    op.create_table(
        "bot_action_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_id", sa.String(length=80), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("requested_by_name", sa.String(length=100), nullable=True),
        sa.Column("decided_by_name", sa.String(length=100), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_action_approvals_action_type", "bot_action_approvals", ["action_type"], schema=SCHEMA)
    op.create_index("ix_bot_action_approvals_profile_key", "bot_action_approvals", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_action_approvals_status", "bot_action_approvals", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_action_approvals_created_at", "bot_action_approvals", ["created_at"], schema=SCHEMA)
    op.create_index("ix_bot_action_approvals_status_created", "bot_action_approvals", ["status", "created_at"], schema=SCHEMA)

    op.create_table(
        "bot_evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("profile_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), server_default="0", nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["test_case_id"], [f"{SCHEMA}.bot_test_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_evaluation_runs_test_case_id", "bot_evaluation_runs", ["test_case_id"], schema=SCHEMA)
    op.create_index("ix_bot_evaluation_runs_profile_key", "bot_evaluation_runs", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_evaluation_runs_status", "bot_evaluation_runs", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_evaluation_runs_created_at", "bot_evaluation_runs", ["created_at"], schema=SCHEMA)
    op.create_index("ix_bot_evaluation_runs_profile_created", "bot_evaluation_runs", ["profile_key", "created_at"], schema=SCHEMA)
    op.create_index("ix_bot_evaluation_runs_status_created", "bot_evaluation_runs", ["status", "created_at"], schema=SCHEMA)

    op.create_table(
        "bot_intent_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phrase", sa.String(length=200), nullable=False),
        sa.Column("profile_key", sa.String(length=80), nullable=True),
        sa.Column("expected_skills", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_intent_corrections_phrase", "bot_intent_corrections", ["phrase"], schema=SCHEMA)
    op.create_index("ix_bot_intent_corrections_profile_key", "bot_intent_corrections", ["profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_intent_corrections_status", "bot_intent_corrections", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_intent_corrections_created_at", "bot_intent_corrections", ["created_at"], schema=SCHEMA)

    op.create_table(
        "bot_collaboration_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("lead_profile_key", sa.String(length=80), nullable=False),
        sa.Column("participant_profiles", sa.JSON(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_records", sa.JSON(), nullable=False),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_collaboration_runs_lead_profile_key", "bot_collaboration_runs", ["lead_profile_key"], schema=SCHEMA)
    op.create_index("ix_bot_collaboration_runs_status", "bot_collaboration_runs", ["status"], schema=SCHEMA)
    op.create_index("ix_bot_collaboration_runs_created_at", "bot_collaboration_runs", ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_bot_collaboration_runs_created_at", "bot_collaboration_runs"),
        ("ix_bot_collaboration_runs_status", "bot_collaboration_runs"),
        ("ix_bot_collaboration_runs_lead_profile_key", "bot_collaboration_runs"),
        ("ix_bot_intent_corrections_created_at", "bot_intent_corrections"),
        ("ix_bot_intent_corrections_status", "bot_intent_corrections"),
        ("ix_bot_intent_corrections_profile_key", "bot_intent_corrections"),
        ("ix_bot_intent_corrections_phrase", "bot_intent_corrections"),
        ("ix_bot_evaluation_runs_status_created", "bot_evaluation_runs"),
        ("ix_bot_evaluation_runs_profile_created", "bot_evaluation_runs"),
        ("ix_bot_evaluation_runs_created_at", "bot_evaluation_runs"),
        ("ix_bot_evaluation_runs_status", "bot_evaluation_runs"),
        ("ix_bot_evaluation_runs_profile_key", "bot_evaluation_runs"),
        ("ix_bot_evaluation_runs_test_case_id", "bot_evaluation_runs"),
        ("ix_bot_action_approvals_status_created", "bot_action_approvals"),
        ("ix_bot_action_approvals_created_at", "bot_action_approvals"),
        ("ix_bot_action_approvals_status", "bot_action_approvals"),
        ("ix_bot_action_approvals_profile_key", "bot_action_approvals"),
        ("ix_bot_action_approvals_action_type", "bot_action_approvals"),
        ("ix_bot_tasks_type_status", "bot_tasks"),
        ("ix_bot_tasks_profile_status", "bot_tasks"),
        ("ix_bot_tasks_created_at", "bot_tasks"),
        ("ix_bot_tasks_status", "bot_tasks"),
        ("ix_bot_tasks_profile_key", "bot_tasks"),
        ("ix_bot_tasks_task_type", "bot_tasks"),
    ):
        op.drop_index(index_name, table_name=table_name, schema=SCHEMA)
    for table_name in (
        "bot_collaboration_runs",
        "bot_intent_corrections",
        "bot_evaluation_runs",
        "bot_action_approvals",
        "bot_tasks",
    ):
        op.drop_table(table_name, schema=SCHEMA)
    for index_name in (
        "ix_bot_test_cases_priority",
        "ix_bot_knowledge_files_expires_at",
        "ix_bot_knowledge_files_owner_profile_key",
        "ix_bot_knowledge_files_visibility_scope",
        "ix_bot_knowledge_files_review_status",
    ):
        table = "bot_test_cases" if "test_cases" in index_name else "bot_knowledge_files"
        op.drop_index(index_name, table_name=table, schema=SCHEMA)
    for column_name in ("last_run_at", "last_result", "priority", "required_evidence"):
        op.drop_column("bot_test_cases", column_name, schema=SCHEMA)
    for column_name in ("expires_at", "version", "tags", "owner_profile_key", "visibility_scope", "review_status"):
        op.drop_column("bot_knowledge_files", column_name, schema=SCHEMA)
