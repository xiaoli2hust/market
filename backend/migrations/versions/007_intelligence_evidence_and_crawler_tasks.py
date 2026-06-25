"""add intelligence evidence fields and crawler task tables.

Revision ID: 007_intelligence_evidence_and_crawler_tasks
Revises: 006_report_versions
Create Date: 2026-06-23
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "007_intelligence_evidence_and_crawler_tasks"
down_revision = "006_report_versions"
branch_labels = None
depends_on = None

SCHEMA = os.getenv("DATABASE_SCHEMA") or "marketing"


def upgrade() -> None:
    op.add_column("crawler_items", sa.Column("amount_wan", sa.Float(), nullable=True), schema=SCHEMA)
    op.add_column("crawler_items", sa.Column("buyer", sa.String(length=200), nullable=True), schema=SCHEMA)
    op.add_column("crawler_items", sa.Column("region", sa.String(length=100), nullable=True), schema=SCHEMA)
    op.add_column("crawler_items", sa.Column("notice_type", sa.String(length=80), nullable=True), schema=SCHEMA)
    op.add_column(
        "crawler_items",
        sa.Column("matched_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
    )

    op.create_index("ix_crawler_items_amount_wan", "crawler_items", ["amount_wan"], schema=SCHEMA)
    op.create_index("ix_crawler_items_buyer", "crawler_items", ["buyer"], schema=SCHEMA)
    op.create_index("ix_crawler_items_region", "crawler_items", ["region"], schema=SCHEMA)
    op.create_index("ix_crawler_items_notice_type", "crawler_items", ["notice_type"], schema=SCHEMA)
    op.create_index("ix_crawler_items_category_amount", "crawler_items", ["category", "amount_wan"], schema=SCHEMA)
    op.create_index("ix_crawler_items_category_region", "crawler_items", ["category", "region"], schema=SCHEMA)
    op.create_index("ix_crawler_items_category_notice", "crawler_items", ["category", "notice_type"], schema=SCHEMA)

    op.execute(
        f"""
        UPDATE "{SCHEMA}"."crawler_items"
        SET
          amount_wan = COALESCE(
            CASE
              WHEN extra_data ? 'amount_wan' AND (extra_data->>'amount_wan') ~ '^[0-9]+(\\.[0-9]+)?$'
              THEN (extra_data->>'amount_wan')::double precision
            END,
            CASE
              WHEN extra_data ? 'bid_amount' AND (extra_data->>'bid_amount') ~ '^[0-9]+(\\.[0-9]+)?$'
              THEN (extra_data->>'bid_amount')::double precision
            END
          ),
          buyer = NULLIF(extra_data->>'buyer', ''),
          region = COALESCE(NULLIF(extra_data->>'location', ''), NULLIF(extra_data->>'region', '')),
          notice_type = COALESCE(
            NULLIF(extra_data->>'notice_type', ''),
            NULLIF(extra_data->>'subtype', ''),
            NULLIF(extra_data->>'channel', ''),
            NULLIF(extra_data->>'basic_class', '')
          ),
          matched_keywords = CASE
            WHEN jsonb_typeof(extra_data->'matched_keywords') = 'array' THEN extra_data->'matched_keywords'
            WHEN NULLIF(extra_data->>'keywords', '') IS NOT NULL
              THEN to_jsonb(regexp_split_to_array(extra_data->>'keywords', '[,，、\\s]+'))
            ELSE matched_keywords
          END
        WHERE extra_data IS NOT NULL
        """
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evidence_id", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("query_summary", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("data_quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("evidence_id", name="uq_evidence_records_evidence_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_evidence_records_source_type", "evidence_records", ["source_type"], schema=SCHEMA)
    op.create_index("ix_evidence_records_category", "evidence_records", ["category"], schema=SCHEMA)
    op.create_index("ix_evidence_records_record_type", "evidence_records", ["record_type"], schema=SCHEMA)
    op.create_index("ix_evidence_records_record_id", "evidence_records", ["record_id"], schema=SCHEMA)
    op.create_index("ix_evidence_records_record", "evidence_records", ["record_type", "record_id"], schema=SCHEMA)
    op.create_index("ix_evidence_records_category_time", "evidence_records", ["category", "collected_at"], schema=SCHEMA)

    op.create_table(
        "intelligence_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("crawler_item_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_lead_id", sa.Integer(), nullable=True),
        sa.Column("evidence_id", sa.String(length=80), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["crawler_item_id"], [f"{SCHEMA}.crawler_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_lead_id"], [f"{SCHEMA}.opportunity_leads.id"], ondelete="SET NULL"),
        schema=SCHEMA,
    )
    op.create_index("ix_intelligence_events_event_type", "intelligence_events", ["event_type"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_category", "intelligence_events", ["category"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_crawler_item_id", "intelligence_events", ["crawler_item_id"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_opportunity_lead_id", "intelligence_events", ["opportunity_lead_id"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_evidence_id", "intelligence_events", ["evidence_id"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_category_created", "intelligence_events", ["category", "created_at"], schema=SCHEMA)
    op.create_index("ix_intelligence_events_type_created", "intelligence_events", ["event_type", "created_at"], schema=SCHEMA)

    op.create_table(
        "crawler_task_locks",
        sa.Column("name", sa.String(length=80), primary_key=True),
        sa.Column("lock_owner", sa.String(length=120), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_task_locks_locked_until", "crawler_task_locks", ["locked_until"], schema=SCHEMA)

    op.create_table(
        "crawler_task_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("crawler_name", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("trigger_source", sa.String(length=30), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lock_owner", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", name="uq_crawler_task_runs_run_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_crawler_task_runs_crawler_name", "crawler_task_runs", ["crawler_name"], schema=SCHEMA)
    op.create_index("ix_crawler_task_runs_category", "crawler_task_runs", ["category"], schema=SCHEMA)
    op.create_index("ix_crawler_task_runs_status", "crawler_task_runs", ["status"], schema=SCHEMA)
    op.create_index("ix_crawler_task_runs_name_created", "crawler_task_runs", ["crawler_name", "created_at"], schema=SCHEMA)
    op.create_index("ix_crawler_task_runs_status_created", "crawler_task_runs", ["status", "created_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_crawler_task_runs_status_created", table_name="crawler_task_runs", schema=SCHEMA)
    op.drop_index("ix_crawler_task_runs_name_created", table_name="crawler_task_runs", schema=SCHEMA)
    op.drop_index("ix_crawler_task_runs_status", table_name="crawler_task_runs", schema=SCHEMA)
    op.drop_index("ix_crawler_task_runs_category", table_name="crawler_task_runs", schema=SCHEMA)
    op.drop_index("ix_crawler_task_runs_crawler_name", table_name="crawler_task_runs", schema=SCHEMA)
    op.drop_table("crawler_task_runs", schema=SCHEMA)

    op.drop_index("ix_crawler_task_locks_locked_until", table_name="crawler_task_locks", schema=SCHEMA)
    op.drop_table("crawler_task_locks", schema=SCHEMA)

    op.drop_index("ix_intelligence_events_type_created", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_category_created", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_evidence_id", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_opportunity_lead_id", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_crawler_item_id", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_category", table_name="intelligence_events", schema=SCHEMA)
    op.drop_index("ix_intelligence_events_event_type", table_name="intelligence_events", schema=SCHEMA)
    op.drop_table("intelligence_events", schema=SCHEMA)

    op.drop_index("ix_evidence_records_category_time", table_name="evidence_records", schema=SCHEMA)
    op.drop_index("ix_evidence_records_record", table_name="evidence_records", schema=SCHEMA)
    op.drop_index("ix_evidence_records_record_id", table_name="evidence_records", schema=SCHEMA)
    op.drop_index("ix_evidence_records_record_type", table_name="evidence_records", schema=SCHEMA)
    op.drop_index("ix_evidence_records_category", table_name="evidence_records", schema=SCHEMA)
    op.drop_index("ix_evidence_records_source_type", table_name="evidence_records", schema=SCHEMA)
    op.drop_table("evidence_records", schema=SCHEMA)

    op.drop_index("ix_crawler_items_category_notice", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_category_region", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_category_amount", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_notice_type", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_region", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_buyer", table_name="crawler_items", schema=SCHEMA)
    op.drop_index("ix_crawler_items_amount_wan", table_name="crawler_items", schema=SCHEMA)
    op.drop_column("crawler_items", "matched_keywords", schema=SCHEMA)
    op.drop_column("crawler_items", "notice_type", schema=SCHEMA)
    op.drop_column("crawler_items", "region", schema=SCHEMA)
    op.drop_column("crawler_items", "buyer", schema=SCHEMA)
    op.drop_column("crawler_items", "amount_wan", schema=SCHEMA)
