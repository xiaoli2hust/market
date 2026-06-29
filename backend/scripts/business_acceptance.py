"""Business acceptance checks for Market product.

Run from repository root:
    python3 backend/scripts/business_acceptance.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_bidding_express_period() -> None:
    from app.services import bidding_express_service as service

    original_fetch = service.fetch_bidding_data

    def fake_fetch(_api_key: str):
        return [
            {
                "title": "公安一张图空间智能平台建设项目",
                "buyer": "某市公安局",
                "bidamount": "200",
                "publishtime": "2026-06-23",
                "subtype": "招标公告",
                "s_matchkey": "公安,地图,空间智能",
            },
            {
                "title": "自然资源实景三维平台升级项目",
                "buyer": "某市自然资源局",
                "bidamount": "350",
                "publishtime": "2026-06-02",
                "subtype": "中标公告",
                "s_matchkey": "自然资源,实景三维,地理信息",
            },
            {
                "title": "旧年度泛信息化项目",
                "buyer": "某单位",
                "bidamount": "50",
                "publishtime": "2026-05-10",
                "subtype": "招标公告",
                "s_matchkey": "信息化",
            },
        ], "验收客户"

    service.fetch_bidding_data = fake_fetch
    try:
        week = service.build_express("acceptance", "2026-06-23", period="week")
        month = service.build_express("acceptance", "2026-06-23", period="month")
        all_time = service.build_express("acceptance", "2026-06-23", period="all")
    finally:
        service.fetch_bidding_data = original_fetch

    assert week.source_total == 3, "来源总数应保留，不能被周期过滤吞掉"
    assert week.total == 1, "本周只应命中 2026-06-22 至 2026-06-28 的公告"
    assert month.total == 2, "本月应命中 6 月内公告"
    assert all_time.total == 3, "全部周期应保留来源返回的所有公告"
    assert week.period_label == "06.22-06.28", "周期标签应表达真实统计窗口"


def check_scheduler_per_crawler_contract() -> None:
    scheduler = _read("backend/app/services/crawler_scheduler.py")
    config_router = _read("backend/app/routers/crawler_config.py")
    management = _read("frontend/src/pages/Management/index.tsx")
    crawler_router = _read("backend/app/routers/crawler.py")
    crawler_base = _read("backend/app/crawlers/base.py")
    diagnostics = _read("backend/app/crawlers/diagnostics.py")
    official_crawler = _read("backend/app/crawlers/official_crawler.py")
    bidding_crawler = _read("backend/app/crawlers/bidding_crawler.py")
    market_crawler = _read("backend/app/crawlers/market_crawler.py")
    competitor_crawler = _read("backend/app/crawlers/competitor_crawler.py")
    ai_crawler = _read("backend/app/crawlers/ai_crawler.py")
    crawler_config = _read("backend/app/crawlers/config.py")
    models = _read("backend/app/models.py")
    assert "select(CrawlerRunLog)" in scheduler and "CrawlerRunLog.crawler_name == name" in scheduler, "调度必须按爬虫查询最近运行记录"
    assert "CRAWLER_FAILURE_RETRY_AFTER" in scheduler, "失败采集必须有快速重试窗口"
    assert (
        "due_names" in scheduler
        and 'execute_crawlers(db, due_names, trigger_source="schedule")' in scheduler
    ), "调度必须只运行到期爬虫，并标记为系统调度来源"
    assert "crawler_next_runs" in scheduler, "调度状态必须暴露每个爬虫的下次运行"
    assert "_start_crawler_heartbeat" in crawler_router, "长时间采集必须持续续租任务锁"
    assert "CRAWLER_TASK_HEARTBEAT_INTERVAL_SECONDS" in crawler_router, "任务锁心跳间隔必须显式配置"
    assert "build_crawler_run_diagnostics" in crawler_router, "采集运行日志必须写入工程化诊断报告"
    assert "_update_crawler_source_health" in crawler_router, "采集诊断必须回写到来源运行状态"
    assert "_source_is_in_cooldown" in crawler_router and "cooldown_until" in models, "异常来源必须支持冷却跳过"
    assert "latest_by_source" in crawler_base and "last_cursor" in models, "来源必须记录最近入库水位线"
    assert "include_protected: bool = True" in crawler_router, "非标讯内置来源不能因为受保护而脱离后台运行口径"
    assert 'include_protected=False' in crawler_router, "标讯授权主链路必须与公开候选源分开运行"
    assert 'setattr(crawler, "sources", db_sources)' in crawler_router, "非标讯采集运行必须优先使用后台来源配置"
    assert "raw_by_source" in crawler_base and "data_quality" in crawler_base, "采集统计必须按来源和字段质量沉淀"
    assert "_retry_after_seconds" in crawler_base and 'resp.headers.get("Retry-After")' in crawler_base, "采集限流必须尊重 Retry-After"
    assert "_last_request_at_by_origin" in crawler_base, "采集限速必须按域名隔离，不能用整轮全局限速代替"
    assert "If-None-Match" in crawler_base and "If-Modified-Since" in crawler_base, "公开网页采集必须支持增量条件请求"
    assert "discover_feed_urls" in crawler_base, "低风险公开源必须支持订阅/站点地图发现"
    assert (
        "_looks_like_js_challenge(" in crawler_base
        and "_decode_response_bytes(resp.content)" in crawler_base
    ), "安全挑战页不能被当作有效正文解析，且不得先访问 resp.text 导致编码修正失效"
    assert "normalize_crawl_policy" in crawler_router and '"crawl_policy": crawl_policy' in crawler_router, "运行时来源必须携带来源级反爬策略"
    assert "CRAWLER_MAX_ITEMS_PER_RUN" in crawler_config, "采集必须区分每来源限量与整轮总量保护"
    for source_name, crawler_source in {
        "政策": official_crawler,
        "市场线索": market_crawler,
        "竞对": competitor_crawler,
        "行业知识": ai_crawler,
    }.items():
        assert "CRAWLER_MAX_ITEMS_PER_RUN" in crawler_source, f"{source_name}采集不能用单来源上限截断整轮来源覆盖"
    for marker in ("diagnosis_code", "next_action", "anti_crawl_level", "quality_summary"):
        assert marker in diagnostics, f"采集诊断必须包含 {marker}"
    for name, source in {
        "政策": official_crawler,
        "公开标讯": bidding_crawler,
        "市场线索": market_crawler,
        "竞对": competitor_crawler,
    }.items():
        assert "detail_fetched" in source and "详情页" in source, f"{name}采集必须支持低频详情页补全文本"
        assert '"crawl_policy":' in source, f"{name}来源运行报告必须携带来源级反爬策略"
    assert '"crawl_policy":' in ai_crawler, "行业知识来源运行报告必须携带来源级反爬策略"
    assert "crawler_next_runs" in config_router, "管理接口必须返回逐爬虫调度计划"
    assert "runtime_status" in config_router and "last_checked_at" in config_router, "管理接口必须返回来源运行状态"
    assert "last_cursor" in config_router, "管理接口必须返回来源最近入库水位线"
    assert "mgmt-schedule-agents" in management, "管理后台必须展示逐 Agent 调度计划"
    assert "CRAWLER_RUN_STATUS_META" in management, "管理后台必须把爬虫状态转成业务可读文案"
    assert "本次采集诊断" in management and "金额率" in management, "管理后台必须展示来源诊断和字段质量"
    assert "SOURCE_RUNTIME_META" in management and "运行状态" in management, "管理后台必须展示来源级运行健康"
    assert "SOURCE_RISK_META" in management and "反爬级别" in management, "管理后台必须展示来源反爬级别"
    assert "最近入库" in management, "管理后台必须提示来源最近入库水位线"


def check_intelligence_agent_pages() -> None:
    page = _read("frontend/src/pages/Intelligence/index.tsx")
    for category in ("bidding", "policy", "news", "competitor", "ai"):
        assert f"category: '{category}'" in page, f"市场洞察必须加载 {category} 分析"
    assert "竞对监控 Agent" in page, "竞对监控必须是独立 Agent 页"
    assert "行业知识 Agent" in page, "行业知识必须是独立 Agent 页"
    assert "EvidenceRecordList" in page, "Agent 分析必须展示证据记录"


def check_report_lifecycle_contract() -> None:
    models = _read("backend/app/models.py")
    service = _read("backend/app/services/report_service.py")
    reports = _read("backend/app/routers/reports.py")
    migration = _read("backend/migrations/versions/006_report_versions.py")
    dashboard = _read("frontend/src/pages/Dashboard/index.tsx")
    assert "version:" in models and "superseded_at" in models, "报告模型必须包含版本和归档时间"
    assert "_prepare_report_version" in service, "生成报告前必须计算版本并归档可替换草稿"
    assert '_supersede_peer_reports' in reports and 'status = "published"' in reports, "推送成功必须发布当前版本并归档同周期旧版本"
    assert "006_report_versions" in migration, "正式迁移必须覆盖报告版本字段"
    assert "v{record.version" in dashboard and "已归档" in dashboard, "前端必须展示报告版本和归档态"


def check_bidding_express_frontend_contract() -> None:
    api = _read("frontend/src/services/api.ts")
    dashboard = _read("frontend/src/pages/Dashboard/index.tsx")
    router = _read("backend/app/routers/bidding_express.py")
    assert "period_label" in api and "source_total" in api, "标讯速递接口类型必须返回周期和来源总数"
    assert "biddingPeriod" in dashboard and "generateBiddingExpress({" in dashboard, "前端生成标讯速递必须传入周期"
    assert '"status": "ok" if express.total else "empty"' in router, "空周期必须返回 empty 状态"


def run_check(name: str, fn: Callable[[], None]) -> bool:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def main() -> int:
    checks = [
        ("标讯速递周期口径", check_bidding_express_period),
        ("采集调度逐 Agent 运行", check_scheduler_per_crawler_contract),
        ("五类市场洞察 Agent 页面", check_intelligence_agent_pages),
        ("报告版本与发布生命周期", check_report_lifecycle_contract),
        ("标讯速递前端业务口径", check_bidding_express_frontend_contract),
    ]
    passed = sum(1 for name, fn in checks if run_check(name, fn))
    print(f"\n{passed}/{len(checks)} business checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
