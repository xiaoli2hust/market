"""add aipaas config and crawler item quality flags.

Revision ID: 016_aipaas_config_and_crawler_item_flags
Revises: 015_bot_enterprise_operations
Create Date: 2026-06-29
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "016_aipaas_config_and_crawler_item_flags"
down_revision = "015_bot_enterprise_operations"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column(
        "crawler_items",
        sa.Column("is_invalid", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "crawler_items",
        sa.Column("invalid_reason", sa.String(length=500), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_items_is_invalid", "crawler_items", ["is_invalid"], schema=SCHEMA)

    op.create_table(
        "aipaas_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("app_id", sa.String(length=255), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sync_interval_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("sync_users", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_result", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("aipaas_configs", schema=SCHEMA)
    op.drop_index("ix_crawler_items_is_invalid", table_name="crawler_items", schema=SCHEMA)
    op.drop_column("crawler_items", "invalid_reason", schema=SCHEMA)
    op.drop_column("crawler_items", "is_invalid", schema=SCHEMA)
