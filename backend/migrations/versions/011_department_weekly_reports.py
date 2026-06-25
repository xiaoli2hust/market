"""add department weekly report archive.

Revision ID: 011_department_weekly_reports
Revises: 010_dingtalk_app_identity_fields
Create Date: 2026-06-25
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "011_department_weekly_reports"
down_revision = "010_dingtalk_app_identity_fields"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "department_weekly_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=30), server_default="html_upload", nullable=False),
        sa.Column("html_content", sa.Text(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("content_length", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_by", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_department_weekly_reports_department",
        "department_weekly_reports",
        ["department"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_department_weekly_reports_week_start",
        "department_weekly_reports",
        ["week_start"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_department_weekly_reports_week_department",
        "department_weekly_reports",
        ["week_start", "department"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_department_weekly_reports_status_created",
        "department_weekly_reports",
        ["status", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_department_weekly_reports_status_created", table_name="department_weekly_reports", schema=SCHEMA)
    op.drop_index("ix_department_weekly_reports_week_department", table_name="department_weekly_reports", schema=SCHEMA)
    op.drop_index("ix_department_weekly_reports_week_start", table_name="department_weekly_reports", schema=SCHEMA)
    op.drop_index("ix_department_weekly_reports_department", table_name="department_weekly_reports", schema=SCHEMA)
    op.drop_table("department_weekly_reports", schema=SCHEMA)
