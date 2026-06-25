"""add report version and lifecycle status.

Revision ID: 006_report_versions
Revises: 005_secret_column_lengths
Create Date: 2026-06-23
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "006_report_versions"
down_revision = "005_secret_column_lengths"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column(
        "report_pages",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema=SCHEMA,
    )
    op.add_column(
        "report_pages",
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
        schema=SCHEMA,
    )
    op.add_column(
        "report_pages",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        f"""
        UPDATE "{SCHEMA}"."report_pages"
        SET status = CASE WHEN push_status = 'pushed' THEN 'published' ELSE status END
        WHERE status = 'draft'
        """
    )
    op.create_index(
        "ix_report_pages_type_date_status",
        "report_pages",
        ["report_type", "report_date", "status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_report_pages_type_date_status", table_name="report_pages", schema=SCHEMA)
    op.drop_column("report_pages", "superseded_at", schema=SCHEMA)
    op.drop_column("report_pages", "status", schema=SCHEMA)
    op.drop_column("report_pages", "version", schema=SCHEMA)
