"""Export a sanitized Market crawler/data snapshot from local SQLite.

The exporter is intentionally conservative: it does not export `.env`,
encrypted runtime secrets, local database files, uploaded report HTML, or full
third-party article bodies. The resulting JSON is safe to commit and can be
loaded with `import_market_snapshot.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "backend" / "market.db"
DEFAULT_OUTPUT = ROOT / "backend" / "app" / "fixtures" / "market_snapshot.json"
MAX_CONTENT_CHARS = 320

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|access[_-]?key|webhook|cookie|session)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"\bding[a-z0-9]{12,}\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def parse_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                clean[key] = None
            else:
                clean[key] = redact_sensitive(item)
        return clean
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        redacted = value
        for pattern in SENSITIVE_VALUE_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def compact_text(*values: Any, limit: int = MAX_CONTENT_CHARS) -> str | None:
    for value in values:
        if not value:
            continue
        text = re.sub(r"\s+", " ", str(value)).strip()
        if text:
            return text[:limit]
    return None


def rows(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return conn.execute(sql).fetchall()


def export_snapshot(db_path: Path, output_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    crawler_sources: list[dict[str, Any]] = []
    for row in rows(
        conn,
        """
        SELECT category, name, url, base_url, selectors, is_active,
               runtime_status, consecutive_failures, cooldown_until,
               last_checked_at, last_success_at, last_error_at,
               last_diagnosis_code, last_diagnosis_label, last_error_message,
               last_cursor, last_found, last_saved, created_at
        FROM crawler_sources
        ORDER BY category, id
        """,
    ):
        item = dict(row)
        item["selectors"] = redact_sensitive(parse_json(item.get("selectors"), {}))
        item["last_cursor"] = redact_sensitive(parse_json(item.get("last_cursor"), None))
        item["is_active"] = bool(item["is_active"])
        crawler_sources.append(item)

    keyword_configs: list[dict[str, Any]] = []
    for row in rows(conn, "SELECT category, keywords, updated_at FROM keyword_configs ORDER BY category"):
        item = dict(row)
        item["keywords"] = redact_sensitive(parse_json(item.get("keywords"), []))
        keyword_configs.append(item)

    schedule_configs: list[dict[str, Any]] = []
    table_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "schedule_config" in table_names:
        for row in rows(
            conn,
            """
            SELECT crawl_frequency_per_day, relevance_threshold, auto_crawl_enabled, updated_at
            FROM schedule_config
            ORDER BY id
            """,
        ):
            item = dict(row)
            item["auto_crawl_enabled"] = bool(item["auto_crawl_enabled"])
            schedule_configs.append(item)

    crawler_items: list[dict[str, Any]] = []
    for row in rows(
        conn,
        """
        SELECT id, category, title, content, summary, source, source_url,
               published_at, relevance_score, extra_data, is_pushed, created_at,
               amount_wan, buyer, region, notice_type, matched_keywords
        FROM crawler_items
        ORDER BY category, published_at DESC, relevance_score DESC, id
        """,
    ):
        item = dict(row)
        item["source_id"] = item.pop("id")
        item["content_excerpt"] = compact_text(item.pop("content", None), item.get("summary"))
        item["summary"] = compact_text(item.get("summary"), limit=MAX_CONTENT_CHARS)
        item["extra_data"] = redact_sensitive(parse_json(item.get("extra_data"), {}))
        item["matched_keywords"] = redact_sensitive(parse_json(item.get("matched_keywords"), []))
        item["is_pushed"] = bool(item["is_pushed"])
        crawler_items.append(redact_sensitive(item))

    evidence_records: list[dict[str, Any]] = []
    for row in rows(
        conn,
        """
        SELECT evidence_id, source, source_type, category, title, source_url,
               record_type, record_id, query_summary, data, confidence,
               data_quality_flags, event_time, collected_at
        FROM evidence_records
        ORDER BY category, id
        """,
    ):
        item = dict(row)
        item["data"] = redact_sensitive(parse_json(item.get("data"), {}))
        item["data_quality_flags"] = redact_sensitive(parse_json(item.get("data_quality_flags"), []))
        evidence_records.append(redact_sensitive(item))

    opportunity_leads: list[dict[str, Any]] = []
    for row in rows(
        conn,
        """
        SELECT id, project_name, buyer, budget, score, decision, summary,
               why_it_matters, risks, recommended_action, url, source,
               source_category, procurement_method, publish_date, status,
               raw_record, created_at, updated_at
        FROM opportunity_leads
        ORDER BY decision, score DESC, publish_date DESC, id
        """,
    ):
        item = dict(row)
        item["source_id"] = item.pop("id")
        item["why_it_matters"] = redact_sensitive(parse_json(item.get("why_it_matters"), []))
        item["risks"] = redact_sensitive(parse_json(item.get("risks"), []))
        item["recommended_action"] = redact_sensitive(parse_json(item.get("recommended_action"), []))
        item["raw_record"] = redact_sensitive(parse_json(item.get("raw_record"), {}))
        opportunity_leads.append(redact_sensitive(item))

    intelligence_events: list[dict[str, Any]] = []
    for row in rows(
        conn,
        """
        SELECT event_type, category, subject, crawler_item_id, opportunity_lead_id,
               evidence_id, event_time, payload, created_at
        FROM intelligence_events
        ORDER BY category, id
        """,
    ):
        item = dict(row)
        item["payload"] = redact_sensitive(parse_json(item.get("payload"), {}))
        intelligence_events.append(redact_sensitive(item))

    snapshot = {
        "metadata": {
            "name": "Market 数据采集中心采集配置与数据快照",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "local-sqlite-sanitized",
            "copyright_note": "Crawler item bodies are truncated to excerpts; source URLs remain for evidence traceability.",
            "counts": {
                "crawler_sources": len(crawler_sources),
                "keyword_configs": len(keyword_configs),
                "schedule_configs": len(schedule_configs),
                "crawler_items": len(crawler_items),
                "evidence_records": len(evidence_records),
                "intelligence_events": len(intelligence_events),
                "opportunity_leads": len(opportunity_leads),
            },
        },
        "crawler_sources": crawler_sources,
        "keyword_configs": keyword_configs,
        "schedule_configs": schedule_configs,
        "crawler_items": crawler_items,
        "evidence_records": evidence_records,
        "intelligence_events": intelligence_events,
        "opportunity_leads": opportunity_leads,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export sanitized Market snapshot fixture.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    args = parser.parse_args()

    snapshot = export_snapshot(Path(args.db), Path(args.output))
    print(json.dumps(snapshot["metadata"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
