"""initial tables for marketing schema.

Revision ID: 001_initial_tables
Revises:
Create Date: 2026-06-11

手写迁移：在 ``marketing`` schema 下创建 6 张核心表与所需索引。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "marketing"


def upgrade() -> None:
    # 1. 确保 schema 存在（生产环境通常已由 DBA 创建）。
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    # 2. staff
    op.create_table(
        "staff",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("department", sa.String(length=50), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_staff_name"),
        schema=SCHEMA,
    )

    # 3. daily_report_files
    op.create_table(
        "daily_report_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("user_name", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_date", sa.Date(), nullable=False),
        sa.Column("raw_content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "parse_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_daily_report_files_file_date",
        "daily_report_files",
        ["file_date"],
        schema=SCHEMA,
    )

    # 4. activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.String(length=30), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("opportunity", sa.String(length=200), nullable=True),
        sa.Column("opportunity_id", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "is_reviewed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("source_file_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            [f"{SCHEMA}.staff.id"],
            name="fk_activities_staff_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            [f"{SCHEMA}.daily_report_files.id"],
            name="fk_activities_source_file_id",
            ondelete="SET NULL",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_activities_staff_id", "activities", ["staff_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_activities_report_date", "activities", ["report_date"], schema=SCHEMA
    )
    op.create_index(
        "ix_activities_activity_type", "activities", ["activity_type"], schema=SCHEMA
    )
    op.create_index(
        "ix_activities_staff_date",
        "activities",
        ["staff_id", "report_date"],
        schema=SCHEMA,
    )

    # 5. crawler_items
    op.create_table(
        "crawler_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "is_pushed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_crawler_items_category", "crawler_items", ["category"], schema=SCHEMA
    )
    op.create_index(
        "ix_crawler_items_published_at",
        "crawler_items",
        ["published_at"],
        schema=SCHEMA,
    )

    # 6. daily_express
    op.create_table(
        "daily_express",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("express_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("dingtalk_media_id", sa.String(length=200), nullable=True),
        sa.Column(
            "push_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("express_date", name="uq_daily_express_date"),
        schema=SCHEMA,
    )

    # 7. report_pages
    op.create_table(
        "report_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_type", sa.String(length=10), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("access_token", sa.String(length=100), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "push_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("access_token", name="uq_report_pages_access_token"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_report_pages_type_date",
        "report_pages",
        ["report_type", "report_date"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # 反向顺序：先 drop 含外键的子表，再 drop 父表。
    op.drop_index("ix_report_pages_type_date", table_name="report_pages", schema=SCHEMA)
    op.drop_table("report_pages", schema=SCHEMA)

    op.drop_table("daily_express", schema=SCHEMA)

    op.drop_index(
        "ix_crawler_items_published_at", table_name="crawler_items", schema=SCHEMA
    )
    op.drop_index(
        "ix_crawler_items_category", table_name="crawler_items", schema=SCHEMA
    )
    op.drop_table("crawler_items", schema=SCHEMA)

    op.drop_index("ix_activities_staff_date", table_name="activities", schema=SCHEMA)
    op.drop_index(
        "ix_activities_activity_type", table_name="activities", schema=SCHEMA
    )
    op.drop_index("ix_activities_report_date", table_name="activities", schema=SCHEMA)
    op.drop_index("ix_activities_staff_id", table_name="activities", schema=SCHEMA)
    op.drop_table("activities", schema=SCHEMA)

    op.drop_index(
        "ix_daily_report_files_file_date",
        table_name="daily_report_files",
        schema=SCHEMA,
    )
    op.drop_table("daily_report_files", schema=SCHEMA)

    op.drop_table("staff", schema=SCHEMA)
