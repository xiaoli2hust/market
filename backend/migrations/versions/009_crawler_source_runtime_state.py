"""add crawler source runtime state.

Revision ID: 009_crawler_source_runtime_state
Revises: 008_dingtalk_robot_openapi_config
Create Date: 2026-06-24
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "009_crawler_source_runtime_state"
down_revision = "008_dingtalk_robot_openapi_config"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column(
        "crawler_sources",
        sa.Column("runtime_status", sa.String(length=30), nullable=False, server_default="pending"),
        schema=SCHEMA,
    )
    op.add_column(
        "crawler_sources",
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.add_column("crawler_sources", sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_diagnosis_code", sa.String(length=80), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_diagnosis_label", sa.String(length=120), nullable=True), schema=SCHEMA)
    op.add_column("crawler_sources", sa.Column("last_error_message", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column(
        "crawler_sources",
        sa.Column("last_cursor", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "crawler_sources",
        sa.Column("last_found", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.add_column(
        "crawler_sources",
        sa.Column("last_saved", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_sources_runtime_status", "crawler_sources", ["runtime_status"], schema=SCHEMA)
    op.create_index("ix_crawler_sources_cooldown_until", "crawler_sources", ["cooldown_until"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_crawler_sources_cooldown_until", table_name="crawler_sources", schema=SCHEMA)
    op.drop_index("ix_crawler_sources_runtime_status", table_name="crawler_sources", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_saved", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_found", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_cursor", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_error_message", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_diagnosis_label", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_diagnosis_code", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_error_at", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_success_at", schema=SCHEMA)
    op.drop_column("crawler_sources", "last_checked_at", schema=SCHEMA)
    op.drop_column("crawler_sources", "cooldown_until", schema=SCHEMA)
    op.drop_column("crawler_sources", "consecutive_failures", schema=SCHEMA)
    op.drop_column("crawler_sources", "runtime_status", schema=SCHEMA)
