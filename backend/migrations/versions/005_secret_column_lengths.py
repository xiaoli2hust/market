"""widen encrypted secret columns.

Revision ID: 005_secret_column_lengths
Revises: 004_management_runtime_tables
Create Date: 2026-06-23
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "005_secret_column_lengths"
down_revision = "004_management_runtime_tables"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.alter_column("llm_configs", "api_key", type_=sa.String(length=1024), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "secret", type_=sa.String(length=1024), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "app_secret", type_=sa.String(length=1024), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "jianyu_password", type_=sa.String(length=1024), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "jianyu_api_key", type_=sa.String(length=1024), schema=SCHEMA)


def downgrade() -> None:
    op.alter_column("llm_configs", "api_key", type_=sa.String(length=500), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "secret", type_=sa.String(length=255), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "app_secret", type_=sa.String(length=255), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "jianyu_password", type_=sa.String(length=255), schema=SCHEMA)
    op.alter_column("dingtalk_configs", "jianyu_api_key", type_=sa.String(length=255), schema=SCHEMA)
