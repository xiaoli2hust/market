"""Source-level crawler policy helpers.

The crawler policy is intentionally stored inside each source's selectors JSON.
It keeps anti-crawl behaviour visible in management UI without adding another
table before the crawler source contract stabilizes.
"""

from __future__ import annotations

from typing import Any


CRAWL_RISK_PROFILES: dict[str, dict[str, Any]] = {
    "authorized_api": {
        "label": "授权接口",
        "rank": 10,
        "access_level": "authorized",
        "min_interval_seconds": 0.8,
        "max_requests_per_minute": 60,
        "respect_robots": False,
        "use_conditional_request": False,
        "discover_feeds": False,
        "requires_browser": False,
        "fallback_action": "auth_error_visible",
        "anti_crawl_pattern": "授权鉴权、接口限流、失败退避",
        "strategy_steps": ["使用已授权接口", "按关键词分页检索", "入库后做相关性评分和字段抽取"],
        "stop_rules": ["鉴权失败立即停用并提示配置", "接口限流时退避", "不扩展到未授权站点"],
    },
    "public_query_api": {
        "label": "公开查询接口",
        "rank": 20,
        "access_level": "public_api",
        "min_interval_seconds": 6.0,
        "max_requests_per_minute": 10,
        "respect_robots": True,
        "use_conditional_request": False,
        "discover_feeds": False,
        "requires_browser": False,
        "fallback_action": "stop_on_captcha_or_rate_limit",
        "anti_crawl_pattern": "公开查询限速、固定参数、遇到安全挑战停止",
        "strategy_steps": ["只调用公开查询入口", "固定关键词和分页范围", "429/403 后进入冷却"],
        "stop_rules": ["验证码或安全挑战立即停止", "403/429 不高频重试", "不使用代理池绕过"],
    },
    "rss_low": {
        "label": "低风险订阅源",
        "rank": 30,
        "access_level": "public_feed",
        "min_interval_seconds": 2.0,
        "max_requests_per_minute": 30,
        "respect_robots": True,
        "use_conditional_request": True,
        "discover_feeds": False,
        "requires_browser": False,
        "fallback_action": "parse_feed_incrementally",
        "anti_crawl_pattern": "订阅增量、条件请求、按发布时间去重",
        "strategy_steps": ["优先解析 RSS/Atom", "按发布时间增量入库", "只保留命中业务主题的内容"],
        "stop_rules": ["订阅不可达时记录异常", "不改抓网页全文", "重复内容不入库"],
    },
    "normal_public": {
        "label": "普通公开网页",
        "rank": 40,
        "access_level": "public_html",
        "min_interval_seconds": 3.0,
        "max_requests_per_minute": 20,
        "respect_robots": True,
        "use_conditional_request": True,
        "discover_feeds": True,
        "requires_browser": False,
        "fallback_action": "low_frequency_retry_then_cooldown",
        "anti_crawl_pattern": "robots、低频请求、条件请求、解析失败可诊断",
        "strategy_steps": ["优先读取公开列表页", "列表去重后读取详情", "按关键词和相关性过滤"],
        "stop_rules": ["robots 禁止则不抓", "403/429 后降频并冷却", "解析失败不写入业务视图"],
    },
    "medium_static": {
        "label": "中等风险静态页",
        "rank": 50,
        "access_level": "public_html",
        "min_interval_seconds": 5.0,
        "max_requests_per_minute": 12,
        "respect_robots": True,
        "use_conditional_request": True,
        "discover_feeds": True,
        "requires_browser": False,
        "fallback_action": "cooldown_on_failure",
        "anti_crawl_pattern": "指定页面直采、低频访问、失败冷却",
        "strategy_steps": ["只采配置好的页面清单", "按自然年或栏目范围控制", "抽取正文后做主题过滤"],
        "stop_rules": ["页面不存在则停用候选", "连续失败进入冷却", "不扩大扫描目录"],
    },
    "medium_js": {
        "label": "中等风险动态页",
        "rank": 60,
        "access_level": "public_html",
        "min_interval_seconds": 8.0,
        "max_requests_per_minute": 8,
        "respect_robots": True,
        "use_conditional_request": True,
        "discover_feeds": False,
        "requires_browser": False,
        "fallback_action": "candidate_or_direct_page_only",
        "anti_crawl_pattern": "动态入口谨慎接入、只采确认页面、异常即候选",
        "strategy_steps": ["先找稳定公开栏目或直采页", "通过后再启用", "运行时按低频和冷却执行"],
        "stop_rules": ["需要登录或验证码则停止", "不模拟批量用户行为", "未确认栏目不自动启用"],
    },
    "high_js": {
        "label": "高风险渲染站",
        "rank": 70,
        "access_level": "public_browser",
        "min_interval_seconds": 12.0,
        "max_requests_per_minute": 5,
        "respect_robots": True,
        "use_conditional_request": False,
        "discover_feeds": False,
        "requires_browser": True,
        "fallback_action": "browser_whitelist_required",
        "anti_crawl_pattern": "渲染白名单、人工确认、低频执行、挑战即停",
        "strategy_steps": ["先作为候选源", "确认白名单栏目和页面结构", "启用后单源低频运行"],
        "stop_rules": ["验证码/登录/安全挑战立即停止", "不绕过风控", "不做并发渲染采集"],
    },
}


SOURCE_TIER_PROFILES: dict[str, dict[str, Any]] = {
    "authorized_primary": {
        "label": "L1 授权主链路",
        "rank": 10,
        "description": "已授权结构化来源，优先用于稳定采集和业务分析。",
    },
    "authority_national": {
        "label": "L2 国家级权威源",
        "rank": 20,
        "description": "国家部委、国家级交易平台或全国性公共平台，可信度高，默认优先审核。",
    },
    "authority_regional": {
        "label": "L3 地方权威源",
        "rank": 30,
        "description": "省市政府、地方公共资源交易或数据管理部门，适合区域市场监控。",
    },
    "industry_official": {
        "label": "L4 行业/央企源",
        "rank": 40,
        "description": "行业协会、央国企、运营商、电力等公开来源，适合作为专题补充。",
    },
    "subscription_source": {
        "label": "L5 订阅知识源",
        "rank": 50,
        "description": "RSS/Atom 等订阅源，低成本补充行业知识。",
    },
    "competitor_watch": {
        "label": "L6 竞对监控源",
        "rank": 60,
        "description": "竞对官网、产品页、案例页和公开动态，按事件类型监控。",
    },
    "candidate_high_risk": {
        "label": "L7 高风险候选源",
        "rank": 70,
        "description": "动态渲染、强风控或需人工确认的来源，不默认自动采集。",
    },
    "public_candidate": {
        "label": "L8 普通候选源",
        "rank": 80,
        "description": "普通公开页面，需补齐解析规则并通过连通性验证后再启用。",
    },
}


def normalize_crawl_policy(
    selectors_or_policy: dict[str, Any] | None,
    *,
    source_type: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Return a complete policy dict for one crawler source."""

    raw = selectors_or_policy or {}
    if "risk_level" not in raw and "crawl_policy" in raw and isinstance(raw["crawl_policy"], dict):
        raw = raw["crawl_policy"]
    explicit_policy = raw.get("crawl_policy") if isinstance(raw.get("crawl_policy"), dict) else {}
    source_type = source_type or raw.get("type") or raw.get("source_type") or explicit_policy.get("source_type")
    risk_level = str(
        explicit_policy.get("risk_level")
        or raw.get("risk_level")
        or infer_risk_level(source_type, category)
    )
    profile = dict(CRAWL_RISK_PROFILES.get(risk_level, CRAWL_RISK_PROFILES["normal_public"]))
    profile.update({
        "risk_level": risk_level,
        "source_type": source_type or "official_site",
        "category": category,
    })
    for key in (
        "access_level",
        "min_interval_seconds",
        "max_requests_per_minute",
        "respect_robots",
        "use_conditional_request",
        "discover_feeds",
        "requires_browser",
        "fallback_action",
    ):
        if key in raw:
            profile[key] = raw[key]
        if key in explicit_policy:
            profile[key] = explicit_policy[key]

    profile["min_interval_seconds"] = _positive_float(
        profile.get("min_interval_seconds"),
        CRAWL_RISK_PROFILES["normal_public"]["min_interval_seconds"],
    )
    profile["max_requests_per_minute"] = max(1, int(profile.get("max_requests_per_minute") or 1))
    profile["respect_robots"] = bool(profile.get("respect_robots"))
    profile["use_conditional_request"] = bool(profile.get("use_conditional_request"))
    profile["discover_feeds"] = bool(profile.get("discover_feeds"))
    profile["requires_browser"] = bool(profile.get("requires_browser"))
    return profile


def build_source_strategy_profile(source: dict[str, Any]) -> dict[str, Any]:
    """Build an operator-facing strategy profile for one configured source."""

    selectors = source.get("selectors") or {}
    category = source.get("category")
    source_type = selectors.get("type") or selectors.get("source_type") or source.get("type")
    crawl_policy = normalize_crawl_policy(selectors, source_type=source_type, category=category)
    tier = classify_source_tier(source, crawl_policy)
    gaps = source_strategy_gaps(source, crawl_policy)
    strategy_status = _strategy_status(source, crawl_policy, gaps)
    action = _operator_action(strategy_status, crawl_policy, gaps)
    return {
        "source_tier": tier,
        "strategy_status": strategy_status,
        "strategy_status_label": _strategy_status_label(strategy_status),
        "strategy_gaps": gaps,
        "strategy_sort_rank": _strategy_sort_rank(source, crawl_policy, tier, gaps),
        "collection_strategy": _collection_strategy(source, crawl_policy),
        "anti_crawl_plan": crawl_policy.get("anti_crawl_pattern"),
        "strategy_steps": list(crawl_policy.get("strategy_steps") or []),
        "stop_rules": list(crawl_policy.get("stop_rules") or []),
        "operator_action": action,
    }


def classify_source_tier(source: dict[str, Any], crawl_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    selectors = source.get("selectors") or {}
    policy = crawl_policy or normalize_crawl_policy(selectors, category=source.get("category"))
    source_type = str(selectors.get("type") or selectors.get("source_type") or policy.get("source_type") or "")
    category = str(source.get("category") or "")
    name_url = f"{source.get('name') or ''} {source.get('url') or ''} {source.get('base_url') or ''}".lower()
    protected = bool(selectors.get("protected"))

    if protected and source_type == "api":
        code = "authorized_primary"
    elif policy.get("requires_browser") or source_type == "browser":
        code = "candidate_high_risk"
    elif source_type == "rss":
        code = "subscription_source"
    elif category == "competitor":
        code = "competitor_watch"
    elif any(token in name_url for token in ("国务院", "国家", "中央", "财政部", "公安部", "自然资源部", "发改委", "工信部", "gov.cn", "ggzy.gov.cn", "ccgp.gov.cn")):
        code = "authority_national"
    elif any(token in name_url for token in ("省", "市", "自治区", "政务", "数据局", "公共资源", "政府采购", "czt.", "zfcg", "ggzy")):
        code = "authority_regional"
    elif category in {"news", "ai"} or any(token in name_url for token in ("电网", "移动", "联通", "电信", "协会", "交易所", "研究院", "信通院")):
        code = "industry_official"
    else:
        code = "public_candidate"

    profile = dict(SOURCE_TIER_PROFILES[code])
    profile["code"] = code
    return profile


def source_strategy_gaps(
    source: dict[str, Any],
    crawl_policy: dict[str, Any] | None = None,
) -> list[str]:
    selectors = source.get("selectors") or {}
    policy = crawl_policy or normalize_crawl_policy(selectors, category=source.get("category"))
    source_type = str(selectors.get("type") or selectors.get("source_type") or policy.get("source_type") or "official_site")
    gaps: list[str] = []

    if not selectors.get("scope"):
        gaps.append("缺少采集范围说明")
    if not selectors.get("strategy"):
        gaps.append("缺少业务过滤策略")
    if source_type in {"official_site", "http"}:
        if not selectors.get("list"):
            gaps.append("缺少列表解析规则")
        if not selectors.get("title"):
            gaps.append("缺少标题解析规则")
        if not selectors.get("link"):
            gaps.append("缺少链接解析规则")
    elif source_type == "direct_pages" and not selectors.get("pages"):
        gaps.append("缺少直采页面清单")
    elif source_type == "api_post":
        if selectors.get("payload") is None:
            gaps.append("缺少接口查询参数")
        if not selectors.get("records_path"):
            gaps.append("缺少接口结果路径")
    elif source_type == "browser":
        gaps.append("需要渲染采集白名单和人工确认")
    elif source_type == "api" and not selectors.get("protected"):
        gaps.append("需要授权配置或接口接入说明")

    return gaps


def infer_risk_level(source_type: str | None, category: str | None = None) -> str:
    normalized = str(source_type or "official_site").lower()
    if normalized in {"api", "authorized_api"}:
        return "authorized_api"
    if normalized == "api_post":
        return "public_query_api"
    if normalized == "rss":
        return "rss_low"
    if normalized == "browser":
        return "high_js"
    if normalized == "direct_pages":
        return "medium_static" if category != "competitor" else "medium_js"
    return "normal_public"


def policy_summary(policy: dict[str, Any] | None) -> str:
    normalized = normalize_crawl_policy(policy or {})
    return (
        f"{normalized.get('label')}: "
        f"{normalized.get('min_interval_seconds')}s 间隔, "
        f"{normalized.get('max_requests_per_minute')}/分钟, "
        f"{'遵守 robots' if normalized.get('respect_robots') else '授权接口'}"
    )


def _strategy_sort_rank(
    source: dict[str, Any],
    policy: dict[str, Any],
    tier: dict[str, Any],
    gaps: list[str],
) -> int:
    selectors = source.get("selectors") or {}
    active_penalty = 0 if source.get("is_active") else 25
    protected_bonus = -8 if selectors.get("protected") else 0
    gap_penalty = min(len(gaps), 6) * 8
    return int(tier.get("rank") or 99) * 100 + int(policy.get("rank") or 99) + active_penalty + gap_penalty + protected_bonus


def _strategy_status(source: dict[str, Any], policy: dict[str, Any], gaps: list[str]) -> str:
    selectors = source.get("selectors") or {}
    source_type = str(selectors.get("type") or selectors.get("source_type") or policy.get("source_type") or "")
    hard_gaps = [
        gap for gap in gaps
        if not gap.startswith("未显式配置")
        and not gap.startswith("缺少采集范围")
        and not gap.startswith("缺少业务过滤")
    ]
    if policy.get("requires_browser") or source_type == "browser":
        return "candidate_high_risk"
    if hard_gaps:
        return "needs_rules"
    if source.get("is_active"):
        return "ready"
    return "candidate"


def _strategy_status_label(status: str) -> str:
    return {
        "ready": "策略完整",
        "candidate": "候选待启用",
        "needs_rules": "缺规则",
        "candidate_high_risk": "高风险候选",
    }.get(status, "待确认")


def _operator_action(status: str, policy: dict[str, Any], gaps: list[str]) -> str:
    if status == "ready":
        return "保持当前频率运行，观察命中率、日期率、金额率和异常次数。"
    if status == "candidate_high_risk":
        return "先确认公开栏目、robots 和访问稳定性；遇到登录、验证码或安全挑战不要自动采集。"
    if status == "needs_rules":
        return "先补齐解析规则或直采页面清单，再测试连通性和样例抽取。"
    if gaps:
        return "补齐策略缺口后再启用，避免无关来源污染市场洞察。"
    return "作为候选源保留，确认业务价值后再启用。"


def _collection_strategy(source: dict[str, Any], policy: dict[str, Any]) -> str:
    selectors = source.get("selectors") or {}
    if selectors.get("strategy"):
        return str(selectors["strategy"])
    source_type = str(selectors.get("type") or selectors.get("source_type") or policy.get("source_type") or "")
    if source_type == "api":
        return "授权接口分页拉取，按关键词召回后做相关性评分和字段抽取。"
    if source_type == "rss":
        return "订阅源增量解析，按发布时间去重，只保留命中业务主题的内容。"
    if source_type == "direct_pages":
        return "按已确认页面清单直采，提取正文后做主题和客户类型判断。"
    if source_type == "browser":
        return "仅作为高风险候选源，确认白名单和公开栏目后再低频渲染采集。"
    return "公开列表页低频采集，列表去重后读取详情，按关键词和相关性过滤。"


def _positive_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return number if number > 0 else float(fallback)
