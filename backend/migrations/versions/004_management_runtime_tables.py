"""add management and runtime configuration tables.

Revision ID: 004_management_runtime_tables
Revises: 003_crawler_run_logs
Create Date: 2026-06-23
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004_management_runtime_tables"
down_revision = "003_crawler_run_logs"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "crawler_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("selectors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_sources_category", "crawler_sources", ["category"], schema=SCHEMA)

    op.create_table(
        "keyword_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("category", name="uq_keyword_configs_category"),
        schema=SCHEMA,
    )

    op.create_table(
        "schedule_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crawl_frequency_per_day", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("relevance_threshold", sa.Float(), nullable=False, server_default=sa.text("30")),
        sa.Column("auto_crawl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "llm_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(length=100), nullable=False, server_default=sa.text("'deepseek-chat'")),
        sa.Column("api_base_url", sa.String(length=500), nullable=False, server_default=sa.text("'https://api.deepseek.com'")),
        sa.Column("api_key", sa.String(length=500), nullable=True),
        sa.Column("default_temperature", sa.Float(), nullable=False, server_default=sa.text("0.2")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scene", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default=sa.text("0.2")),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default=sa.text("2000")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scene", name="uq_prompt_templates_scene"),
        schema=SCHEMA,
    )

    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scene", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("api_base_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_llm_call_logs_scene", "llm_call_logs", ["scene"], schema=SCHEMA)
    op.create_index("ix_llm_call_logs_status", "llm_call_logs", ["status"], schema=SCHEMA)
    op.create_index("ix_llm_call_logs_created_at", "llm_call_logs", ["created_at"], schema=SCHEMA)
    op.create_index(
        "ix_llm_call_logs_scene_created",
        "llm_call_logs",
        ["scene", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_llm_call_logs_status_created",
        "llm_call_logs",
        ["status", "created_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "system_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username", name="uq_system_users_username"),
        schema=SCHEMA,
    )

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "api_key_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("key_value", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key_value", name="uq_api_key_records_key_value"),
        schema=SCHEMA,
    )

    op.create_table(
        "dingtalk_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column("app_key", sa.String(length=255), nullable=True),
        sa.Column("app_secret", sa.String(length=255), nullable=True),
        sa.Column("jianyu_username", sa.String(length=100), nullable=True),
        sa.Column("jianyu_password", sa.String(length=255), nullable=True),
        sa.Column("jianyu_api_key", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("dingtalk_configs", schema=SCHEMA)
    op.drop_table("api_key_records", schema=SCHEMA)
    op.drop_table("operation_logs", schema=SCHEMA)
    op.drop_table("system_users", schema=SCHEMA)

    op.drop_index("ix_llm_call_logs_status_created", table_name="llm_call_logs", schema=SCHEMA)
    op.drop_index("ix_llm_call_logs_scene_created", table_name="llm_call_logs", schema=SCHEMA)
    op.drop_index("ix_llm_call_logs_created_at", table_name="llm_call_logs", schema=SCHEMA)
    op.drop_index("ix_llm_call_logs_status", table_name="llm_call_logs", schema=SCHEMA)
    op.drop_index("ix_llm_call_logs_scene", table_name="llm_call_logs", schema=SCHEMA)
    op.drop_table("llm_call_logs", schema=SCHEMA)

    op.drop_table("prompt_templates", schema=SCHEMA)
    op.drop_table("llm_configs", schema=SCHEMA)
    op.drop_table("schedule_config", schema=SCHEMA)
    op.drop_table("keyword_configs", schema=SCHEMA)
    op.drop_index("ix_crawler_sources_category", table_name="crawler_sources", schema=SCHEMA)
    op.drop_table("crawler_sources", schema=SCHEMA)
