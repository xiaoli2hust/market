"""add dingtalk app identity fields.

Revision ID: 010_dingtalk_app_identity_fields
Revises: 009_crawler_source_runtime_state
Create Date: 2026-06-24
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "010_dingtalk_app_identity_fields"
down_revision = "009_crawler_source_runtime_state"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column("dingtalk_configs", sa.Column("app_id", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("dingtalk_configs", sa.Column("agent_id", sa.String(length=255), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("dingtalk_configs", "agent_id", schema=SCHEMA)
    op.drop_column("dingtalk_configs", "app_id", schema=SCHEMA)
