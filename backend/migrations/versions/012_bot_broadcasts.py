"""add bot broadcast records.

Revision ID: 012_bot_broadcasts
Revises: 011_department_weekly_reports
Create Date: 2026-06-25
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "012_bot_broadcasts"
down_revision = "011_department_weekly_reports"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "bot_broadcasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=30), server_default="markdown", nullable=False),
        sa.Column("target_type", sa.String(length=40), server_default="configured_group", nullable=False),
        sa.Column("target_summary", sa.String(length=255), nullable=True),
        sa.Column("target_payload", sa.JSON(), nullable=True),
        sa.Column("at_all", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.Column("sent_by", sa.Integer(), nullable=True),
        sa.Column("sent_by_name", sa.String(length=100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_bot_broadcasts_status", "bot_broadcasts", ["status"], schema=SCHEMA)
    op.create_index(
        "ix_bot_broadcasts_status_created",
        "bot_broadcasts",
        ["status", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_bot_broadcasts_target_created",
        "bot_broadcasts",
        ["target_type", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_bot_broadcasts_target_created", table_name="bot_broadcasts", schema=SCHEMA)
    op.drop_index("ix_bot_broadcasts_status_created", table_name="bot_broadcasts", schema=SCHEMA)
    op.drop_index("ix_bot_broadcasts_status", table_name="bot_broadcasts", schema=SCHEMA)
    op.drop_table("bot_broadcasts", schema=SCHEMA)
