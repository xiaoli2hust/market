"""Crawler strategy and source coverage acceptance checks.

Run from repository root:
    python3 backend/scripts/crawler_coverage_acceptance.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.seed_data import ensure_default_crawler_sources_sqlite  # noqa: E402
from app.crawlers.policy import build_source_strategy_profile  # noqa: E402

_TMP_DIR = tempfile.TemporaryDirectory()
DB_PATH = Path(_TMP_DIR.name) / "crawler_coverage.db"


def _bootstrap_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE crawler_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                base_url TEXT,
                selectors TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        ensure_default_crawler_sources_sqlite(conn)
        conn.commit()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _selectors(row: sqlite3.Row) -> dict:
    try:
        return json.loads(row["selectors"] or "{}")
    except json.JSONDecodeError:
        return {}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _source_ready(row: sqlite3.Row) -> bool:
    selectors = _selectors(row)
    source_type = selectors.get("type") or selectors.get("source_type") or "official_site"
    category = row["category"]
    if category == "bidding":
        if source_type in {"api", "browser"}:
            return False
        if source_type == "direct_pages":
            return bool(selectors.get("pages"))
        return bool(selectors.get("list") and selectors.get("title"))
    if source_type == "browser":
        return False
    if source_type == "rss":
        return category == "ai"
    if source_type == "direct_pages":
        return bool(selectors.get("pages"))
    if source_type == "api_post":
        return bool(selectors.get("payload") is not None and selectors.get("records_path"))
    if source_type == "api":
        return False
    return bool(selectors.get("list") and selectors.get("title"))


def check_active_source_floor() -> None:
    expected = {
        "bidding": 5,
        "policy": 10,
        "news": 9,
        "competitor": 8,
        "ai": 16,
    }
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT category, COUNT(*) AS cnt
            FROM crawler_sources
            WHERE is_active = 1
            GROUP BY category
            """
        ).fetchall()
    counts = {row["category"]: int(row["cnt"]) for row in rows}
    for category, floor in expected.items():
        assert counts.get(category, 0) >= floor, f"{category} active sources below floor: {counts.get(category, 0)} < {floor}"


def check_active_sources_are_runtime_ready() -> None:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT category, name, selectors
            FROM crawler_sources
            WHERE is_active = 1
            ORDER BY category, name
            """
        ).fetchall()
    not_ready = [
        f"{row['category']}:{row['name']}"
        for row in rows
        if not _source_ready(row) and row["category"] != "bidding"
    ]
    assert not not_ready, "active sources not runtime-ready: " + ", ".join(not_ready)


def check_bidding_mainline_is_authorized_only() -> None:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT category, name, selectors
            FROM crawler_sources
            WHERE category = 'bidding' AND is_active = 1
            """
        ).fetchall()
    protected = [row for row in rows if _selectors(row).get("protected")]
    public_ready = [row for row in rows if not _selectors(row).get("protected") and _source_ready(row)]
    assert len(protected) == 1, f"bidding should keep exactly one authorized mainline source, got {len(protected)}"
    selectors = _selectors(protected[0])
    assert selectors.get("type") == "api", "bidding mainline must be protected authorized API"
    assert len(public_ready) >= 4, f"bidding public sources below floor: {len(public_ready)} < 4"


def check_competitor_priority_sources() -> None:
    required = {"吉奥时空/武大吉奥", "京东与图/京图开放平台", "海致科技"}
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT name, selectors
            FROM crawler_sources
            WHERE category = 'competitor' AND is_active = 1
            """
        ).fetchall()
    active = {row["name"] for row in rows}
    missing = sorted(required - active)
    assert not missing, "priority competitor sources missing: " + ", ".join(missing)
    for row in rows:
        selectors = _selectors(row)
        source_type = selectors.get("type") or "official_site"
        assert (
            (source_type == "direct_pages" and selectors.get("pages"))
            or (selectors.get("list") and selectors.get("title"))
        ), f"competitor source lacks runnable parser: {row['name']}"


def check_policy_market_industry_mix() -> None:
    with _connect() as conn:
        active_names = {
            row["name"]
            for row in conn.execute("SELECT name FROM crawler_sources WHERE is_active = 1").fetchall()
        }
    for name in [
        "全国公共资源交易平台",
        "北京市公共资源交易服务平台",
        "浙江省公共资源交易服务平台",
        "南方电网供应链统一服务平台",
        "工业和信息化部政策文件",
        "中央网信办",
        "中国政府网政策文件",
        "国家能源局政府信息公开",
        "国家标准化管理委员会",
        "泰伯网",
        "北极星电力网",
        "C114通信网",
        "国家能源局新闻中心",
        "中国移动新闻中心",
        "中国电信新闻中心",
        "中科星图 GEOVIS",
        "中地数码 MapGIS",
        "航天宏图",
        "OpenAI News",
        "Google AI Blog",
        "Hugging Face Blog",
        "arXiv cs.AI",
        "OSGeo Foundation News",
    ]:
        assert name in active_names, f"coverage source not active: {name}"


def check_industry_knowledge_spatial_contract() -> None:
    config = _read("backend/app/crawlers/config.py")
    ai_crawler = _read("backend/app/crawlers/ai_crawler.py")
    agent = _read("backend/app/crawlers/intelligence_agent.py")
    router = _read("backend/app/routers/crawler.py")

    for marker in (
        "空间数据",
        "GIS平台",
        "地理信息",
        "地址治理",
        "POI数据",
        "遥感",
        "高精地图",
    ):
        assert marker in config, f"行业知识关键词缺少空间数据口径: {marker}"
    assert "OSGeo Foundation News" in config, "行业知识默认源必须包含稳定可运行的空间数据知识源"
    for marker in (
        "QGIS.org Blog",
        "OpenStreetMap Blog",
        "GeoServer Blog",
        "GeoTools Blog",
    ):
        assert marker in config, f"行业知识默认源缺少空间数据源: {marker}"
    assert "SPATIAL_TRUSTED_SOURCE_KEYWORDS" in ai_crawler, "可信空间源必须有独立命中口径"
    assert "空间数据治理" in ai_crawler and "地理编码" in ai_crawler, "行业知识采集器必须允许空间数据标题命中"
    assert '"空间数据"' in agent and "地址治理" in agent, "情报 Agent 必须能识别空间数据主题"
    assert "空间数据/GIS" in router, "管理端采集策略必须说明空间数据/GIS业务范围"


def check_candidate_source_inventory() -> None:
    required = {
        "bidding": {
            "中国铁塔电子采购平台",
            "中国政府采购网采购意向",
            "广东省公共资源交易平台",
            "深圳公共资源交易中心",
            "广州公共资源交易中心",
        },
        "policy": {
            "财政部政府采购政策",
            "上海数据交易所",
            "北京国际大数据交易所",
            "深圳数据交易所",
            "广东省政务服务和数据管理局",
            "浙江省数据局",
        },
        "news": {
            "数字中国建设峰会",
            "中国国际大数据产业博览会",
            "世界人工智能大会",
            "中国测绘学会",
            "移动云新闻中心",
            "天翼云新闻中心",
            "联通数科",
            "国网数科",
        },
        "competitor": {
            "苍穹数码",
            "正元地信",
            "百度地图开放平台",
            "高德开放平台",
            "腾讯位置服务",
            "华为云城市智能体",
            "阿里云城市大脑",
        },
        "ai": {
            "Anthropic News",
            "LangChain Blog",
            "LlamaIndex Blog",
            "NVIDIA Technical Blog",
            "OGC News",
            "Esri Blog",
            "QGIS.org Blog",
            "OpenStreetMap Blog",
            "GeoServer Blog",
            "GeoTools Blog",
        },
    }
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT category, name, selectors
            FROM crawler_sources
            ORDER BY category, name
            """
        ).fetchall()
    by_category: dict[str, set[str]] = {}
    selectors_by_name: dict[str, dict] = {}
    for row in rows:
        by_category.setdefault(row["category"], set()).add(row["name"])
        selectors_by_name[row["name"]] = _selectors(row)

    for category, names in required.items():
        missing = sorted(names - by_category.get(category, set()))
        assert not missing, f"{category} candidate sources missing: " + ", ".join(missing)
    for name in set().union(*required.values()):
        selectors = selectors_by_name.get(name) or {}
        assert selectors.get("risk_level"), f"candidate source lacks anti-crawl risk level: {name}"


def check_all_sources_have_executable_rules() -> None:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT category, name, url, base_url, selectors, is_active
            FROM crawler_sources
            ORDER BY category, name
            """
        ).fetchall()
    broken: list[str] = []
    for row in rows:
        selectors = _selectors(row)
        source_type = selectors.get("type") or selectors.get("source_type") or "official_site"
        strategy = build_source_strategy_profile({
            "category": row["category"],
            "name": row["name"],
            "url": row["url"],
            "base_url": row["base_url"],
            "selectors": selectors,
            "is_active": bool(row["is_active"]),
        })
        if strategy["strategy_status"] in {"needs_rules", "candidate_high_risk"}:
            broken.append(f"{row['category']}:{row['name']}:{strategy['strategy_gaps']}")
            continue
        if source_type in {"official_site", "http"}:
            required = ("list", "title", "link", "rule_profile", "rule_status")
            missing = [key for key in required if not selectors.get(key)]
            if missing:
                broken.append(f"{row['category']}:{row['name']}:missing {','.join(missing)}")
        elif source_type == "direct_pages" and not selectors.get("pages"):
            broken.append(f"{row['category']}:{row['name']}:missing pages")
        elif source_type == "rss" and (row["category"] != "ai" or not selectors.get("rule_profile")):
            broken.append(f"{row['category']}:{row['name']}:rss not executable")
        elif source_type == "browser":
            broken.append(f"{row['category']}:{row['name']}:browser source must be converted to safe public rule")
    assert not broken, "sources without executable crawler rules: " + "; ".join(broken)


def check_crawler_policy_contract() -> None:
    policy = _read("backend/app/crawlers/policy.py")
    base = _read("backend/app/crawlers/base.py")
    crawler_router = _read("backend/app/routers/crawler.py")
    config_router = _read("backend/app/routers/crawler_config.py")
    management = _read("frontend/src/pages/Management/index.tsx")

    for marker in (
        "CRAWL_RISK_PROFILES",
        "normalize_crawl_policy",
        "authorized_api",
        "normal_public",
        "medium_js",
        "high_js",
    ):
        assert marker in policy, f"source-level crawler policy missing marker: {marker}"
    assert "_last_request_at_by_origin" in base and "_origin_key(url)" in base, "采集限速必须按域名隔离"
    assert "_respect_interval(robots_url" in base, "robots.txt 探测也必须纳入域名限速"
    assert "_policy_interval_seconds" in base and "max_requests_per_minute" in base, "采集频率必须由来源策略控制"
    assert "If-None-Match" in base and "If-Modified-Since" in base, "公开网页必须支持条件请求"
    assert "discover_feed_urls" in base and "/sitemap.xml" in base and "/rss.xml" in base, "低风险公开源必须支持订阅/站点地图发现"
    assert '"crawl_policy": crawl_policy' in crawler_router, "运行时来源必须携带 crawl_policy"
    assert '"risk_level": crawl_policy.get("risk_level")' in config_router, "管理接口必须返回反爬级别"
    assert "SOURCE_RISK_META" in management and "反爬级别" in management, "管理后台必须展示反爬级别"


def run_check(name: str, fn: Callable[[], None]) -> bool:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def main() -> int:
    _bootstrap_db()
    checks = [
        ("启用源数量下限", check_active_source_floor),
        ("启用源具备运行配置", check_active_sources_are_runtime_ready),
        ("标讯保持授权主链路", check_bidding_mainline_is_authorized_only),
        ("重点竞对源已接入", check_competitor_priority_sources),
        ("政策/市场/知识覆盖组合", check_policy_market_industry_mix),
        ("行业知识空间数据口径", check_industry_knowledge_spatial_contract),
        ("候选源池覆盖组合", check_candidate_source_inventory),
        ("全部源头具备采集规则", check_all_sources_have_executable_rules),
        ("来源级反爬策略契约", check_crawler_policy_contract),
    ]
    passed = sum(1 for name, fn in checks if run_check(name, fn))
    print(f"\n{passed}/{len(checks)} crawler coverage checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
