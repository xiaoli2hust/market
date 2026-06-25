"""FastAPI 应用入口。

负责装配 lifespan、CORS、路由聚合与健康检查。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text

from . import __version__
from .config import assert_production_security, settings
from .database import dispose_db, engine, init_db
from .routers import api_router
from .routers.reports import public_router as report_public_router
from .routers.express import public_router as express_public_router
from .schemas import HealthResponse
from .seed_data import ensure_default_crawler_sources_sqlite
from .services.crawler_scheduler import start_crawler_scheduler, stop_crawler_scheduler

logger = logging.getLogger(__name__)

# 静态预览页路径：本机零依赖预览看板（无需 Node）。
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """应用生命周期：启动时记录配置，退出时释放数据库连接池。"""

    logger.info(
        "starting marketing backend",
        extra={"schema": settings.DATABASE_SCHEMA, "model": settings.LLM_MODEL},
    )
    assert_production_security()
    # 本机 SQLite 开发模式下自动创建缺失表，便于零配置试用。
    if settings.DATABASE_URL.lower().startswith("sqlite"):
        await init_db()
    # 自动迁移：为已有 SQLite 表添加新增的列（安全操作，已有列会跳过）
    _auto_migrate_sqlite()
    start_crawler_scheduler()
    try:
        yield
    finally:
        await stop_crawler_scheduler()
        await dispose_db()
        logger.info("marketing backend stopped")


def _auto_migrate_sqlite() -> None:
    """SQLite 不会自动 ALTER TABLE，启动时补建缺失列。"""
    if not settings.DATABASE_URL.lower().startswith("sqlite"):
        return
    try:
        import sqlite3
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("./", "")
        conn = sqlite3.connect(db_path)
        # DingtalkConfig: 新增 app_key, app_secret 列
        cols = [row[1] for row in conn.execute("PRAGMA table_info(dingtalk_configs)").fetchall()]
        if cols and "app_key" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN app_key VARCHAR(255)")
        if cols and "app_secret" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN app_secret VARCHAR(255)")
        if cols and "app_id" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN app_id VARCHAR(255)")
        if cols and "agent_id" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN agent_id VARCHAR(255)")
        if cols and "delivery_mode" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN delivery_mode VARCHAR(30)")
        if cols and "robot_code" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN robot_code VARCHAR(255)")
        if cols and "open_conversation_id" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN open_conversation_id VARCHAR(255)")
        if cols and "cool_app_code" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN cool_app_code VARCHAR(255)")
        if cols and "jianyu_username" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN jianyu_username VARCHAR(100)")
        if cols and "jianyu_password" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN jianyu_password VARCHAR(255)")
        if cols and "jianyu_api_key" not in cols:
            conn.execute("ALTER TABLE dingtalk_configs ADD COLUMN jianyu_api_key VARCHAR(255)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name VARCHAR(500) NOT NULL,
                buyer VARCHAR(200),
                budget FLOAT NOT NULL DEFAULT 0,
                score INTEGER NOT NULL DEFAULT 0,
                decision VARCHAR(30) NOT NULL,
                summary TEXT,
                why_it_matters JSON NOT NULL DEFAULT '[]',
                risks JSON NOT NULL DEFAULT '[]',
                recommended_action JSON NOT NULL DEFAULT '[]',
                url VARCHAR(500) NOT NULL UNIQUE,
                source VARCHAR(100) NOT NULL DEFAULT 'bidding',
                source_category VARCHAR(100),
                procurement_method VARCHAR(80),
                publish_date DATE,
                status VARCHAR(30) NOT NULL DEFAULT 'new',
                raw_record JSON,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_opportunity_leads_buyer ON opportunity_leads (buyer)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_opportunity_leads_decision ON opportunity_leads (decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_opportunity_leads_publish_date ON opportunity_leads (publish_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_opportunity_leads_status ON opportunity_leads (status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_opportunity_leads_decision_score ON opportunity_leads (decision, score)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_opportunity_leads_status_score ON opportunity_leads (status, score)"
        )
        report_cols = [row[1] for row in conn.execute("PRAGMA table_info(report_pages)").fetchall()]
        if report_cols and "version" not in report_cols:
            conn.execute("ALTER TABLE report_pages ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        if report_cols and "status" not in report_cols:
            conn.execute("ALTER TABLE report_pages ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'draft'")
        if report_cols and "superseded_at" not in report_cols:
            conn.execute("ALTER TABLE report_pages ADD COLUMN superseded_at DATETIME")
        if report_cols:
            conn.execute(
                """
                UPDATE report_pages
                SET status = CASE WHEN push_status = 'pushed' THEN 'published' ELSE status END
                WHERE status = 'draft'
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_report_pages_type_date_status ON report_pages (report_type, report_date, status)"
            )
        source_cols = [row[1] for row in conn.execute("PRAGMA table_info(crawler_sources)").fetchall()]
        if source_cols:
            for column_name, ddl in {
                "runtime_status": "VARCHAR(30) NOT NULL DEFAULT 'pending'",
                "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
                "cooldown_until": "DATETIME",
                "last_checked_at": "DATETIME",
                "last_success_at": "DATETIME",
                "last_error_at": "DATETIME",
                "last_diagnosis_code": "VARCHAR(80)",
                "last_diagnosis_label": "VARCHAR(120)",
                "last_error_message": "TEXT",
                "last_cursor": "JSON",
                "last_found": "INTEGER NOT NULL DEFAULT 0",
                "last_saved": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if column_name not in source_cols:
                    conn.execute(f"ALTER TABLE crawler_sources ADD COLUMN {column_name} {ddl}")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_sources_runtime_status ON crawler_sources (runtime_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_sources_cooldown_until ON crawler_sources (cooldown_until)")
        _auto_migrate_intelligence_sqlite(conn)
        ensure_default_crawler_sources_sqlite(conn)
        _encrypt_legacy_sqlite_secrets(conn)
        _hash_legacy_sqlite_api_keys(conn)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("SQLite auto-migrate skipped: %s", e)


def _auto_migrate_intelligence_sqlite(conn) -> None:
    """Create intelligence/crawler task tables and backfill structured crawler fields."""

    import json
    import re

    crawler_cols = [row[1] for row in conn.execute("PRAGMA table_info(crawler_items)").fetchall()]
    if crawler_cols:
        for column_name, ddl in {
            "amount_wan": "FLOAT",
            "buyer": "VARCHAR(200)",
            "region": "VARCHAR(100)",
            "notice_type": "VARCHAR(80)",
            "matched_keywords": "JSON",
        }.items():
            if column_name not in crawler_cols:
                conn.execute(f"ALTER TABLE crawler_items ADD COLUMN {column_name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_items_amount_wan ON crawler_items (amount_wan)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_items_buyer ON crawler_items (buyer)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_items_region ON crawler_items (region)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_items_notice_type ON crawler_items (notice_type)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_crawler_items_category_amount ON crawler_items (category, amount_wan)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_crawler_items_category_region ON crawler_items (category, region)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_crawler_items_category_notice ON crawler_items (category, notice_type)"
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id VARCHAR(80) NOT NULL UNIQUE,
            source VARCHAR(200),
            source_type VARCHAR(50) NOT NULL,
            category VARCHAR(30) NOT NULL,
            title VARCHAR(500) NOT NULL,
            source_url VARCHAR(500),
            record_type VARCHAR(50) NOT NULL,
            record_id INTEGER,
            query_summary TEXT,
            data JSON,
            confidence FLOAT NOT NULL DEFAULT 1.0,
            data_quality_flags JSON NOT NULL DEFAULT '[]',
            event_time DATETIME,
            collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_evidence_records_source_type ON evidence_records (source_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_evidence_records_category ON evidence_records (category)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_evidence_records_record_type ON evidence_records (record_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_evidence_records_record_id ON evidence_records (record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_evidence_records_record ON evidence_records (record_type, record_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_records_category_time ON evidence_records (category, collected_at)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS intelligence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type VARCHAR(50) NOT NULL,
            category VARCHAR(30) NOT NULL,
            subject VARCHAR(500) NOT NULL,
            crawler_item_id INTEGER,
            opportunity_lead_id INTEGER,
            evidence_id VARCHAR(80),
            event_time DATETIME,
            payload JSON,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_intelligence_events_event_type ON intelligence_events (event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_intelligence_events_category ON intelligence_events (category)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_intelligence_events_crawler_item_id ON intelligence_events (crawler_item_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_intelligence_events_opportunity_lead_id ON intelligence_events (opportunity_lead_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_intelligence_events_evidence_id ON intelligence_events (evidence_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_intelligence_events_category_created ON intelligence_events (category, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_intelligence_events_type_created ON intelligence_events (event_type, created_at)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crawler_task_locks (
            name VARCHAR(80) PRIMARY KEY,
            lock_owner VARCHAR(120),
            locked_at DATETIME,
            locked_until DATETIME,
            heartbeat_at DATETIME,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_crawler_task_locks_locked_until ON crawler_task_locks (locked_until)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crawler_task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id VARCHAR(80) NOT NULL UNIQUE,
            crawler_name VARCHAR(50) NOT NULL,
            category VARCHAR(30) NOT NULL,
            trigger_source VARCHAR(30) NOT NULL DEFAULT 'manual',
            status VARCHAR(20) NOT NULL,
            lock_owner VARCHAR(120),
            started_at DATETIME,
            finished_at DATETIME,
            heartbeat_at DATETIME,
            duration_ms INTEGER,
            result_summary JSON,
            error_message TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_task_runs_crawler_name ON crawler_task_runs (crawler_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_task_runs_category ON crawler_task_runs (category)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_crawler_task_runs_status ON crawler_task_runs (status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_crawler_task_runs_name_created ON crawler_task_runs (crawler_name, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_crawler_task_runs_status_created ON crawler_task_runs (status, created_at)"
    )

    if not crawler_cols:
        return

    rows = conn.execute(
        """
        SELECT id, category, title, source, source_url, published_at, created_at,
               summary, content, extra_data, relevance_score,
               amount_wan, buyer, region, notice_type, matched_keywords
        FROM crawler_items
        """
    ).fetchall()
    for row in rows:
        (
            item_id,
            category,
            title,
            source,
            source_url,
            published_at,
            created_at,
            summary,
            content,
            raw_extra,
            relevance_score,
            current_amount,
            current_buyer,
            current_region,
            current_notice_type,
            current_keywords,
        ) = row
        extra = _sqlite_json_object(raw_extra)
        amount_wan = current_amount or _sqlite_amount_wan(extra, f"{summary or ''} {content or ''} {title or ''}", re)
        buyer = current_buyer or _sqlite_clean(extra.get("buyer") or extra.get("customer") or extra.get("purchaser"), 200, re)
        region = current_region or _sqlite_clean(extra.get("location") or extra.get("region") or extra.get("area"), 100, re)
        notice_type = current_notice_type or _sqlite_notice_type(extra, re)
        keywords = current_keywords or json.dumps(_sqlite_matched_keywords(extra, re), ensure_ascii=False)
        conn.execute(
            """
            UPDATE crawler_items
            SET amount_wan = ?, buyer = ?, region = ?, notice_type = ?, matched_keywords = ?
            WHERE id = ?
            """,
            (amount_wan, buyer, region, notice_type, keywords, item_id),
        )

        evidence_id = f"EV-{str(category).upper()}-{item_id}"
        data = {
            "amount_wan": amount_wan,
            "buyer": buyer,
            "region": region,
            "notice_type": notice_type,
            "matched_keywords": _sqlite_matched_keywords(extra, re),
            "relevance_score": relevance_score,
        }
        flags = []
        if not source_url:
            flags.append("missing_source_url")
        if not published_at:
            flags.append("missing_published_at")
        if category == "bidding" and not amount_wan:
            flags.append("missing_amount")
        confidence = min(max(float(relevance_score or 50) / 100, 0), 1)
        conn.execute(
            """
            INSERT OR IGNORE INTO evidence_records (
                evidence_id, source, source_type, category, title, source_url,
                record_type, record_id, query_summary, data, confidence,
                data_quality_flags, event_time, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'crawler_item', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                source,
                str(extra.get("source_type") or category),
                category,
                title,
                source_url,
                item_id,
                f"{category} 采集入库：{str(title or '')[:160]}",
                json.dumps(data, ensure_ascii=False),
                confidence,
                json.dumps(flags, ensure_ascii=False),
                published_at,
                created_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO intelligence_events (
                event_type, category, subject, crawler_item_id, evidence_id, event_time, payload, created_at
            )
            SELECT 'item_collected', ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM intelligence_events
                WHERE event_type = 'item_collected' AND crawler_item_id = ?
            )
            """,
            (
                category,
                title,
                item_id,
                evidence_id,
                published_at,
                json.dumps(data, ensure_ascii=False),
                created_at,
                item_id,
            ),
        )


def _sqlite_json_object(value) -> dict:
    import json

    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sqlite_amount_wan(extra: dict, text: str, re_module) -> float | None:
    for key in ("amount_wan", "bid_amount", "bidamount", "budget", "amount"):
        amount = _sqlite_parse_amount_to_wan(extra.get(key), re_module)
        if amount > 0:
            return round(amount, 4)
    cleaned = re_module.sub(r"\s+", "", str(text or "").replace(",", ""))
    for pattern in (
        r"(?:预算金额|预算价|项目预算|采购预算|最高限价|控制价|招标控制价|中标金额|成交金额|中标价|成交价|报价金额|合同金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
        r"(?:人民币|金额)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)(亿元|亿|万元|万|元)",
    ):
        match = re_module.search(pattern, cleaned)
        if match:
            amount = _sqlite_parse_amount_to_wan("".join(match.groups()), re_module)
            if amount > 0:
                return round(amount, 4)
    return None


def _sqlite_parse_amount_to_wan(value, re_module) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    match = re_module.search(r"([0-9]+(?:\.[0-9]+)?)(\s*(亿元|亿|万元|万|元))?", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(3) or "").strip()
    if unit in {"亿元", "亿"}:
        return amount * 10000
    if unit == "元":
        return amount / 10000
    return amount


def _sqlite_matched_keywords(extra: dict, re_module) -> list[str]:
    raw_values = [extra.get("matched_keywords"), extra.get("keywords"), extra.get("query_keyword")]
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not raw:
            continue
        if isinstance(raw, list):
            parts = [str(part).strip() for part in raw]
        else:
            parts = [part.strip() for part in re_module.split(r"[,，、\s]+", str(raw)) if part.strip()]
        for part in parts:
            if not part or len(part) > 24:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(part)
    return result[:12]


def _sqlite_notice_type(extra: dict, re_module) -> str | None:
    direct = _sqlite_clean(extra.get("notice_type"), 80, re_module)
    if direct:
        return direct
    text = " ".join(str(extra.get(key) or "") for key in ("subtype", "channel", "basic_class"))
    for pattern in (
        "公开招标", "招标公告", "竞争性磋商", "询价", "单一来源", "采购意向",
        "更正公告", "中标结果", "成交结果", "候选人公示", "调研公告", "废标", "流标",
    ):
        if pattern in text:
            return pattern
    if "中标" in text:
        return "中标结果"
    if "成交" in text:
        return "成交结果"
    if "招标" in text:
        return "招标公告"
    if "公示" in text:
        return "公示"
    return _sqlite_clean(text, 80, re_module)


def _sqlite_clean(value, limit: int, re_module) -> str | None:
    text = re_module.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else None


def _encrypt_legacy_sqlite_secrets(conn) -> None:
    """Encrypt legacy plaintext runtime secrets in the local SQLite database."""

    from .secret_store import encrypt_secret, is_encrypted_secret

    def protect(value: str | None) -> str | None:
        if not value or is_encrypted_secret(value):
            return value
        return encrypt_secret(value)

    for table, fields in {
        "dingtalk_configs": ["webhook_url", "secret", "app_secret", "jianyu_password", "jianyu_api_key"],
        "llm_configs": ["api_key"],
    }.items():
        rows = conn.execute(f"SELECT id, {', '.join(fields)} FROM {table}").fetchall()
        for row in rows:
            row_id = row[0]
            updates: dict[str, str | None] = {}
            for index, field in enumerate(fields, start=1):
                current = row[index]
                protected = protect(current)
                if protected != current:
                    updates[field] = protected
            if not updates:
                continue
            set_clause = ", ".join(f"{field} = ?" for field in updates)
            conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?",
                [*updates.values(), row_id],
            )


def _hash_legacy_sqlite_api_keys(conn) -> None:
    """Replace legacy plaintext upload API keys with non-reversible hashes."""

    from .secret_store import hash_api_key, is_hashed_api_key

    rows = conn.execute("SELECT id, key_value FROM api_key_records").fetchall()
    for key_id, key_value in rows:
        if not key_value or is_hashed_api_key(key_value):
            continue
        conn.execute(
            "UPDATE api_key_records SET key_value = ? WHERE id = ?",
            (hash_api_key(key_value), key_id),
        )


app = FastAPI(
    title="Market 数据采集中心 API",
    description="面向部门日报周报、市场洞察研判、商机推进预测与系统管理的后端服务。",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# 公开分享链接：/r/{token} 和 /re/{token}，不带 /api 前缀、不需要 JWT 认证
app.include_router(report_public_router)
app.include_router(express_public_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """根路径指向 API 文档；正式产品入口由前端服务提供。"""

    return RedirectResponse(url="/api/docs")


@app.get("/preview", include_in_schema=False)
async def preview_page() -> FileResponse:
    """内置的零依赖看板预览页，直接调用 /api/* 渲染活动数据。"""

    if not settings.ENABLE_LOCAL_PREVIEW:
        raise HTTPException(status_code=404, detail="local preview is disabled")
    return FileResponse(STATIC_DIR / "preview.html", media_type="text/html")


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness：进程存活即可返回。"""

    return HealthResponse(status="ok", version=__version__)


@app.get("/api/ready", response_model=HealthResponse, tags=["system"])
async def readiness() -> HealthResponse:
    """Readiness：确认数据库可连接，供容器编排决定是否接流量。"""

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("readiness check failed")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthResponse(status="ready", version=__version__)
