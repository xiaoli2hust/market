"""add dingtalk robot openapi configuration.

Revision ID: 008_dingtalk_robot_openapi_config
Revises: 007_intelligence_evidence_and_crawler_tasks
Create Date: 2026-06-24
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "008_dingtalk_robot_openapi_config"
down_revision = "007_intelligence_evidence_and_crawler_tasks"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column("dingtalk_configs", sa.Column("delivery_mode", sa.String(length=30), nullable=True), schema=SCHEMA)
    op.add_column("dingtalk_configs", sa.Column("robot_code", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("dingtalk_configs", sa.Column("open_conversation_id", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("dingtalk_configs", sa.Column("cool_app_code", sa.String(length=255), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("dingtalk_configs", "cool_app_code", schema=SCHEMA)
    op.drop_column("dingtalk_configs", "open_conversation_id", schema=SCHEMA)
    op.drop_column("dingtalk_configs", "robot_code", schema=SCHEMA)
    op.drop_column("dingtalk_configs", "delivery_mode", schema=SCHEMA)
