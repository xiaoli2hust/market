"""Crawler engineering acceptance checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_crawler_runtime_guard_contract() -> None:
    crawler_router = _read("backend/app/routers/crawler.py")
    crawler_base = _read("backend/app/crawlers/base.py")
    bidding_crawler = _read("backend/app/crawlers/bidding_crawler.py")
    diagnostics = _read("backend/app/crawlers/diagnostics.py")
    assert "CRAWLER_RUN_TIMEOUT_BY_NAME" in crawler_router, "采集总控必须配置逐引擎运行上限"
    assert "asyncio.wait_for(" in crawler_router, "采集总控必须用有界运行防止后台长时间灰锁"
    assert "except asyncio.TimeoutError" in crawler_router, "采集超时必须写日志并释放任务锁"
    assert "except asyncio.CancelledError" in crawler_router, "手动中断或服务停止必须释放任务锁"
    assert "_record_crawler_runtime_failure" in crawler_router, "采集运行失败必须统一收敛任务结束和锁释放"
    assert '"network_error"' in crawler_router and "timedelta(hours=6)" in crawler_router, "网络异常来源必须进入冷却"
    assert '"not_found"' in crawler_router and "timedelta(days=7)" in crawler_router, "失效地址必须进入长冷却"
    assert '"parser_failed"' in crawler_router and "timedelta(hours=12)" in crawler_router, "解析失效来源必须进入冷却"
    assert 'report.get("status") in {"error", "skipped"}' in crawler_base, "跳过的关键来源不能被当作正常采集"
    assert "settings.JIANYU_USERNAME" in bidding_crawler, "结构化标讯爬虫必须兼容既有启动配置"
    assert "settings.JIANYU_PASSWORD" in bidding_crawler, "结构化标讯爬虫必须兼容既有启动配置"
    assert "_persist_discovered_api_key" in bidding_crawler, "结构化标讯自动发现的 Key 必须沉淀到运行时配置"
    for marker in ("ssl", "certificate", "nodename", "name resolution"):
        assert marker in diagnostics, f"采集诊断必须识别网络/证书/DNS异常：{marker}"
