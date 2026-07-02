"""Crawler run diagnostics.

This module turns raw crawler counters into operator-facing health reports:
which sources worked, why a source failed, what can be fixed next, and how
complete the saved data is.
"""

from __future__ import annotations

import re
from typing import Any

from .base import CrawlStats
from .policy import normalize_crawl_policy, policy_summary


def build_crawler_run_diagnostics(
    *,
    crawler_name: str,
    category: str,
    stats: CrawlStats,
) -> dict[str, Any]:
    reports = [
        enrich_source_report(
            report,
            category=category,
            raw_count=stats.raw_by_source,
            saved_count=stats.saved_by_source,
            duplicate_count=stats.duplicate_by_source,
            discarded_count=stats.discarded_by_source,
            latest_by_source=stats.latest_by_source,
        )
        for report in (stats.source_reports or [])
        if isinstance(report, dict)
    ]
    return {
        "source_reports": reports,
        "health_summary": _health_summary(reports),
        "quality_summary": _quality_summary(category, stats),
        "engineering_strategy": _engineering_strategy(crawler_name, category),
    }


def enrich_source_report(
    report: dict[str, Any],
    *,
    category: str,
    raw_count: dict[str, int] | None = None,
    saved_count: dict[str, int] | None = None,
    duplicate_count: dict[str, int] | None = None,
    discarded_count: dict[str, int] | None = None,
    latest_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    name = str(report.get("name") or report.get("source") or "未命名来源")
    status = str(report.get("status") or "unknown")
    diagnosis = classify_source_report(report)
    source_type = _source_type(report, category)
    crawl_policy = normalize_crawl_policy(report.get("crawl_policy") or report, source_type=source_type, category=category)
    return {
        **report,
        "name": name,
        "source_type": source_type,
        "risk_level": crawl_policy.get("risk_level"),
        "crawl_policy": crawl_policy,
        "status": status,
        "status_label": _status_label(status),
        "diagnosis_code": diagnosis["code"],
        "diagnosis_label": diagnosis["label"],
        "severity": diagnosis["severity"],
        "next_action": diagnosis["next_action"],
        "anti_crawl_level": policy_summary(crawl_policy),
        "compliance": _compliance(report, source_type),
        "raw_count": int((raw_count or {}).get(name, 0)),
        "saved_count": int((saved_count or {}).get(name, 0)),
        "duplicate_count": int((duplicate_count or {}).get(name, 0)),
        "discarded_count": int((discarded_count or {}).get(name, 0)),
        "latest_item": (latest_by_source or {}).get(name),
    }


def classify_source_report(report: dict[str, Any]) -> dict[str, str]:
    status = str(report.get("status") or "").lower()
    error = str(report.get("error") or report.get("message") or "")
    text = error.lower()

    if status == "ok":
        found = int(report.get("found") or 0)
        if found <= 0:
            return _diag("no_match", "本次无命中", "warn", "检查关键词是否过窄，或等待下一轮更新")
        return _diag("ok", "采集正常", "ok", "保持当前频率和解析规则")

    if status == "skipped":
        return _diag("missing_config", "配置缺失", "warn", "补齐授权 Key、账号密码或启用规则后重试")

    if "robots.txt" in text or "robots" in text:
        return _diag("robots_blocked", "robots 限制", "warn", "不要绕过限制；改用授权接口或人工加入候选源")
    if "验证码" in error or "captcha" in text or "安全挑战" in error or "challenge" in text:
        return _diag("challenge_detected", "验证码/安全挑战", "warn", "停止自动采集；改用授权接口、RSS 或低频人工确认源")
    if "429" in text or "too many" in text or "rate" in text:
        return _diag("rate_limited", "站点限流", "warn", "降低频率，延长退避窗口，避免连续触发")
    if "403" in text or "forbidden" in text:
        return _diag("forbidden", "访问被拒绝", "warn", "检查公开访问权限；不要使用代理池或绕过登录")
    if "404" in text or "not found" in text:
        return _diag("not_found", "页面不存在", "error", "更新来源地址或停用该源")
    if (
        "timeout" in text
        or "timed out" in text
        or "connect" in text
        or "ssl" in text
        or "certificate" in text
        or "nodename" in text
        or "name resolution" in text
    ):
        return _diag("network_error", "网络或超时", "warn", "稍后重试；连续失败时降级来源")
    if "selector" in text or "解析" in error or "parse" in text:
        return _diag("parser_failed", "解析规则失效", "error", "更新列表、标题、链接、日期选择器")
    if "key 未配置" in error or "未配置" in error or "登录失败" in error:
        return _diag("missing_config", "配置缺失", "warn", "在管理后台补齐授权配置并测试连接")

    if status == "error":
        return _diag("unknown_error", "采集异常", "error", "查看错误详情，确认是源失效、网络问题还是解析规则问题")
    return _diag("unknown", "状态未知", "warn", "刷新运行日志或重新运行该采集引擎")


def _diag(code: str, label: str, severity: str, next_action: str) -> dict[str, str]:
    return {
        "code": code,
        "label": label,
        "severity": severity,
        "next_action": next_action,
    }


def _health_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(reports)
    ok = sum(1 for report in reports if report.get("status") == "ok" and int(report.get("found") or 0) > 0)
    empty = sum(1 for report in reports if report.get("status") == "ok" and int(report.get("found") or 0) <= 0)
    skipped = sum(1 for report in reports if report.get("status") == "skipped")
    errors = sum(1 for report in reports if report.get("status") == "error")
    blocked = sum(
        1
        for report in reports
        if report.get("diagnosis_code") in {"robots_blocked", "challenge_detected", "forbidden", "rate_limited"}
    )
    return {
        "total_sources": total,
        "ok_sources": ok,
        "empty_sources": empty,
        "skipped_sources": skipped,
        "error_sources": errors,
        "blocked_sources": blocked,
        "ok_rate": round(ok / total, 4) if total else 0,
        "status": "healthy" if errors == 0 and skipped == 0 else ("partial" if ok > 0 else "attention"),
    }


def _quality_summary(category: str, stats: CrawlStats) -> dict[str, Any]:
    quality = dict(stats.data_quality or {})
    saved = int(quality.get("saved_items") or 0)

    def ratio(key: str) -> float:
        if saved <= 0:
            return 0.0
        return round(int(quality.get(key) or 0) / saved, 4)

    result = {
        "saved_items": saved,
        "source_url_rate": ratio("with_source_url"),
        "published_at_rate": ratio("with_published_at"),
        "summary_rate": ratio("with_summary_or_content"),
        "relevance_score_rate": ratio("with_relevance_score"),
        "duplicate_ratio": round(stats.duplicates_skipped / max(stats.total_found, 1), 4),
        "discard_ratio": round(stats.low_score_discarded / max(stats.total_found, 1), 4),
        "quality_flags": [],
    }
    flags: list[str] = result["quality_flags"]
    if saved == 0 and stats.total_found > 0:
        flags.append("found_but_not_saved")
    if result["published_at_rate"] < 0.6 and saved >= 3:
        flags.append("low_date_coverage")
    if result["source_url_rate"] < 0.8 and saved >= 3:
        flags.append("low_url_coverage")
    if result["duplicate_ratio"] > 0.5 and stats.total_found >= 5:
        flags.append("high_duplicate_ratio")
    if result["discard_ratio"] > 0.7 and stats.total_found >= 5:
        flags.append("keyword_too_broad_or_low_fit")

    if category == "bidding":
        result.update({
            "amount_rate": ratio("with_amount"),
            "buyer_rate": ratio("with_buyer"),
            "notice_type_rate": ratio("with_notice_type"),
        })
        if result["amount_rate"] < 0.4 and saved >= 3:
            flags.append("low_amount_coverage")
        if result["buyer_rate"] < 0.5 and saved >= 3:
            flags.append("low_buyer_coverage")

    return result


def _engineering_strategy(crawler_name: str, category: str) -> dict[str, Any]:
    strategy_by_category = {
        "bidding": {
            "levels": ["授权结构化接口", "公开站点低频补充", "人工候选源复核"],
            "stop_rules": ["验证码/安全挑战立即停止", "robots 禁止则不抓", "403/429 不重试高频请求"],
            "quality_gate": ["金额", "采购人", "地区", "公告类型", "关键词命中"],
        },
        "policy": {
            "levels": ["权威政策站", "地方政策站", "年度直采页"],
            "stop_rules": ["只抓公开页面", "不绕过登录", "年度窗口过滤"],
            "quality_gate": ["发布日期", "政策主题", "客户类型", "影响等级"],
        },
        "news": {
            "levels": ["政府/行业官网", "行业媒体", "直采页"],
            "stop_rules": ["低频访问", "无命中不入库", "导航页过滤"],
            "quality_gate": ["来源链接", "发布日期", "主题命中", "摘要"],
        },
        "competitor": {
            "levels": ["竞对官网", "案例/新闻页", "公开中标线索"],
            "stop_rules": ["只采公开信息", "不做登录绕过", "普通导航不入库"],
            "quality_gate": ["竞对名称", "事件类型", "客户/区域/产品动作"],
        },
        "ai": {
            "levels": ["RSS 优先", "官网公开页", "论文/知识源"],
            "stop_rules": ["订阅源优先", "网页低频", "无业务主题不入库"],
            "quality_gate": ["主题", "来源", "摘要", "推荐动作"],
        },
    }
    return {
        "crawler_name": crawler_name,
        "category": category,
        **strategy_by_category.get(category, strategy_by_category["news"]),
    }


def _source_type(report: dict[str, Any], category: str) -> str:
    explicit = report.get("source_type") or report.get("type")
    if explicit:
        return str(explicit)
    name_url = f"{report.get('name') or ''} {report.get('url') or ''}".lower()
    if category == "bidding" and ("结构化" in name_url or "jianyu360" in name_url):
        return "authorized_api"
    if report.get("query_keywords"):
        return "query_api"
    if "rss" in name_url or "feed" in name_url:
        return "rss"
    if re.search(r"/20\d{2}", name_url):
        return "direct_page"
    return "official_html"


def _anti_crawl_level(source_type: str) -> str:
    mapping = {
        "authorized_api": "授权接口：限速、鉴权、错误可见",
        "query_api": "公开查询接口：低频 POST、验证码停止、按关键词分页",
        "rss": "订阅源：低频拉取、按发布时间去重",
        "direct_page": "直采页：逐页低频、只取公开内容",
        "official_html": "公开网页：robots、限速、退避、解析失败可诊断",
    }
    return mapping.get(source_type, "公开来源：低频、退避、失败可诊断")


def _compliance(report: dict[str, Any], source_type: str) -> dict[str, bool]:
    raw = report.get("compliance")
    if isinstance(raw, dict):
        return {
            "robots_checked": bool(raw.get("robots_checked", True)),
            "rate_limited": bool(raw.get("rate_limited", True)),
            "captcha_bypass": bool(raw.get("captcha_bypass", False)),
            "login_bypass": bool(raw.get("login_bypass", False)),
        }
    return {
        "robots_checked": source_type != "authorized_api",
        "rate_limited": True,
        "captcha_bypass": False,
        "login_bypass": False,
    }


def _status_label(status: str) -> str:
    return {
        "ok": "正常",
        "error": "异常",
        "skipped": "跳过",
        "unknown": "未知",
    }.get(status, status or "未知")
