"""Import the sanitized Market crawler/data snapshot.

Run from the repository root:

    PYTHONPATH=backend python3 backend/scripts/import_market_snapshot.py

The import is idempotent. It updates crawler source configuration by
`category + name`, keyword configuration by category, crawler items by source
URL/title, evidence records by evidence id, and opportunity leads by URL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import (
    CrawlerItem,
    CrawlerSource,
    EvidenceRecord,
    IntelligenceEvent,
    KeywordConfig,
    OpportunityLead,
    ScheduleConfig,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "backend" / "app" / "fixtures" / "market_snapshot.json"


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if len(text) == 10:
        return datetime.fromisoformat(text + "T00:00:00")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


async def scalar_one_or_none(session, stmt):
    result = await session.execute(stmt)
    return result.scalars().first()


async def import_snapshot(path: Path) -> dict[str, int]:
    await init_db()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    counts = {
        "crawler_sources": 0,
        "keyword_configs": 0,
        "schedule_configs": 0,
        "crawler_items": 0,
        "opportunity_leads": 0,
        "evidence_records": 0,
        "intelligence_events": 0,
    }

    item_id_map: dict[int, int] = {}
    lead_id_map: dict[int, int] = {}

    async with SessionLocal() as session:
        for item in snapshot.get("crawler_sources", []):
            row = await scalar_one_or_none(
                session,
                select(CrawlerSource).where(
                    CrawlerSource.category == item["category"],
                    CrawlerSource.name == item["name"],
                ),
            )
            if not row:
                row = CrawlerSource(category=item["category"], name=item["name"], url=item["url"])
                session.add(row)
            row.url = item["url"]
            row.base_url = item.get("base_url")
            row.selectors = item.get("selectors") or {}
            row.is_active = bool(item.get("is_active", True))
            row.runtime_status = item.get("runtime_status") or "pending"
            row.consecutive_failures = int(item.get("consecutive_failures") or 0)
            row.cooldown_until = parse_datetime(item.get("cooldown_until"))
            row.last_checked_at = parse_datetime(item.get("last_checked_at"))
            row.last_success_at = parse_datetime(item.get("last_success_at"))
            row.last_error_at = parse_datetime(item.get("last_error_at"))
            row.last_diagnosis_code = item.get("last_diagnosis_code")
            row.last_diagnosis_label = item.get("last_diagnosis_label")
            row.last_error_message = item.get("last_error_message")
            row.last_cursor = item.get("last_cursor")
            row.last_found = int(item.get("last_found") or 0)
            row.last_saved = int(item.get("last_saved") or 0)
            counts["crawler_sources"] += 1

        for item in snapshot.get("keyword_configs", []):
            row = await scalar_one_or_none(
                session,
                select(KeywordConfig).where(KeywordConfig.category == item["category"]),
            )
            if not row:
                row = KeywordConfig(category=item["category"], keywords=[])
                session.add(row)
            row.keywords = item.get("keywords") or []
            counts["keyword_configs"] += 1

        for item in snapshot.get("schedule_configs", []):
            row = await scalar_one_or_none(session, select(ScheduleConfig).order_by(ScheduleConfig.id))
            if not row:
                row = ScheduleConfig()
                session.add(row)
            row.crawl_frequency_per_day = int(item.get("crawl_frequency_per_day") or 2)
            row.relevance_threshold = float(item.get("relevance_threshold") or 30)
            row.auto_crawl_enabled = bool(item.get("auto_crawl_enabled", False))
            counts["schedule_configs"] += 1

        await session.flush()

        for item in snapshot.get("crawler_items", []):
            source_url = item.get("source_url")
            stmt = select(CrawlerItem)
            if source_url:
                stmt = stmt.where(CrawlerItem.source_url == source_url)
            else:
                stmt = stmt.where(CrawlerItem.category == item["category"], CrawlerItem.title == item["title"])
            row = await scalar_one_or_none(session, stmt)
            if not row:
                row = CrawlerItem(category=item["category"], title=item["title"])
                session.add(row)
            row.category = item["category"]
            row.title = item["title"]
            row.content = item.get("content_excerpt") or item.get("summary")
            row.summary = item.get("summary")
            row.source = item.get("source")
            row.source_url = source_url
            row.published_at = parse_date(item.get("published_at"))
            row.relevance_score = item.get("relevance_score")
            row.extra_data = item.get("extra_data") or {}
            row.is_pushed = bool(item.get("is_pushed", False))
            row.amount_wan = item.get("amount_wan")
            row.buyer = item.get("buyer")
            row.region = item.get("region")
            row.notice_type = item.get("notice_type")
            row.matched_keywords = item.get("matched_keywords") or []
            await session.flush()
            if item.get("source_id") is not None:
                item_id_map[int(item["source_id"])] = int(row.id)
            counts["crawler_items"] += 1

        for item in snapshot.get("opportunity_leads", []):
            row = await scalar_one_or_none(session, select(OpportunityLead).where(OpportunityLead.url == item["url"]))
            if not row:
                row = OpportunityLead(project_name=item["project_name"], url=item["url"], decision=item["decision"])
                session.add(row)
            row.project_name = item["project_name"]
            row.buyer = item.get("buyer")
            row.budget = float(item.get("budget") or 0)
            row.score = int(item.get("score") or 0)
            row.decision = item["decision"]
            row.summary = item.get("summary")
            row.why_it_matters = item.get("why_it_matters") or []
            row.risks = item.get("risks") or []
            row.recommended_action = item.get("recommended_action") or []
            row.source = item.get("source") or "bidding"
            row.source_category = item.get("source_category")
            row.procurement_method = item.get("procurement_method")
            row.publish_date = parse_date(item.get("publish_date"))
            row.status = item.get("status") or "new"
            row.raw_record = item.get("raw_record") or {}
            await session.flush()
            if item.get("source_id") is not None:
                lead_id_map[int(item["source_id"])] = int(row.id)
            counts["opportunity_leads"] += 1

        for item in snapshot.get("evidence_records", []):
            row = await scalar_one_or_none(
                session,
                select(EvidenceRecord).where(EvidenceRecord.evidence_id == item["evidence_id"]),
            )
            if not row:
                row = EvidenceRecord(
                    evidence_id=item["evidence_id"],
                    source_type=item["source_type"],
                    category=item["category"],
                    title=item["title"],
                    record_type=item["record_type"],
                )
                session.add(row)
            row.source = item.get("source")
            row.source_type = item["source_type"]
            row.category = item["category"]
            row.title = item["title"]
            row.source_url = item.get("source_url")
            row.record_type = item["record_type"]
            old_record_id = item.get("record_id")
            row.record_id = item_id_map.get(int(old_record_id), old_record_id) if old_record_id is not None else None
            row.query_summary = item.get("query_summary")
            row.data = item.get("data") or {}
            row.confidence = float(item.get("confidence") or 1.0)
            row.data_quality_flags = item.get("data_quality_flags") or []
            row.event_time = parse_datetime(item.get("event_time"))
            row.collected_at = parse_datetime(item.get("collected_at")) or datetime.now()
            counts["evidence_records"] += 1

        for item in snapshot.get("intelligence_events", []):
            old_item_id = item.get("crawler_item_id")
            old_lead_id = item.get("opportunity_lead_id")
            new_item_id = item_id_map.get(int(old_item_id)) if old_item_id is not None else None
            new_lead_id = lead_id_map.get(int(old_lead_id)) if old_lead_id is not None else None
            row = await scalar_one_or_none(
                session,
                select(IntelligenceEvent).where(
                    IntelligenceEvent.event_type == item["event_type"],
                    IntelligenceEvent.category == item["category"],
                    IntelligenceEvent.subject == item["subject"],
                    IntelligenceEvent.evidence_id == item.get("evidence_id"),
                ),
            )
            if not row:
                row = IntelligenceEvent(
                    event_type=item["event_type"],
                    category=item["category"],
                    subject=item["subject"],
                )
                session.add(row)
            row.crawler_item_id = new_item_id
            row.opportunity_lead_id = new_lead_id
            row.evidence_id = item.get("evidence_id")
            row.event_time = parse_datetime(item.get("event_time"))
            row.payload = item.get("payload") or {}
            counts["intelligence_events"] += 1

        await session.commit()

    return counts


async def amain() -> int:
    parser = argparse.ArgumentParser(description="Import sanitized Market snapshot fixture.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Snapshot JSON path")
    args = parser.parse_args()
    counts = await import_snapshot(Path(args.fixture))
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
