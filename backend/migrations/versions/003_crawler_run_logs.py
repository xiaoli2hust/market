"""add crawler run logs.

Revision ID: 003_crawler_run_logs
Revises: 002_opportunity_leads
Create Date: 2026-06-20
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_crawler_run_logs"
down_revision = "002_opportunity_leads"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "crawler_run_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crawler_name", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_found", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("new_saved", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("low_score_discarded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_run_logs_crawler_name", "crawler_run_logs", ["crawler_name"], schema=SCHEMA)
    op.create_index("ix_crawler_run_logs_category", "crawler_run_logs", ["category"], schema=SCHEMA)
    op.create_index("ix_crawler_run_logs_status", "crawler_run_logs", ["status"], schema=SCHEMA)
    op.create_index(
        "ix_crawler_run_logs_name_created",
        "crawler_run_logs",
        ["crawler_name", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_crawler_run_logs_category_created",
        "crawler_run_logs",
        ["category", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_crawler_run_logs_category_created", table_name="crawler_run_logs", schema=SCHEMA)
    op.drop_index("ix_crawler_run_logs_name_created", table_name="crawler_run_logs", schema=SCHEMA)
    op.drop_index("ix_crawler_run_logs_status", table_name="crawler_run_logs", schema=SCHEMA)
    op.drop_index("ix_crawler_run_logs_category", table_name="crawler_run_logs", schema=SCHEMA)
    op.drop_index("ix_crawler_run_logs_crawler_name", table_name="crawler_run_logs", schema=SCHEMA)
    op.drop_table("crawler_run_logs", schema=SCHEMA)
