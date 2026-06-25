"""add opportunity leads.

Revision ID: 002_opportunity_leads
Revises: 001_initial_tables
Create Date: 2026-06-20
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_opportunity_leads"
down_revision = "001_initial_tables"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.create_table(
        "opportunity_leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_name", sa.String(length=500), nullable=False),
        sa.Column("buyer", sa.String(length=200), nullable=True),
        sa.Column("budget", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("why_it_matters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_action", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False, server_default=sa.text("'bidding'")),
        sa.Column("source_category", sa.String(length=100), nullable=True),
        sa.Column("procurement_method", sa.String(length=80), nullable=True),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'new'")),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("url", name="uq_opportunity_leads_url"),
        schema=SCHEMA,
    )
    op.create_index("ix_opportunity_leads_buyer", "opportunity_leads", ["buyer"], schema=SCHEMA)
    op.create_index("ix_opportunity_leads_decision", "opportunity_leads", ["decision"], schema=SCHEMA)
    op.create_index("ix_opportunity_leads_publish_date", "opportunity_leads", ["publish_date"], schema=SCHEMA)
    op.create_index("ix_opportunity_leads_status", "opportunity_leads", ["status"], schema=SCHEMA)
    op.create_index(
        "ix_opportunity_leads_decision_score",
        "opportunity_leads",
        ["decision", "score"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_opportunity_leads_status_score",
        "opportunity_leads",
        ["status", "score"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_leads_status_score", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_index("ix_opportunity_leads_decision_score", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_index("ix_opportunity_leads_status", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_index("ix_opportunity_leads_publish_date", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_index("ix_opportunity_leads_decision", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_index("ix_opportunity_leads_buyer", table_name="opportunity_leads", schema=SCHEMA)
    op.drop_table("opportunity_leads", schema=SCHEMA)
