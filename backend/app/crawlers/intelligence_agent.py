"""情报 Agent 规则层。

第一阶段不让 Agent 替销售做商机判断，只做外部信号的解释：
- 识别业务主题
- 标出影响等级
- 给出轻量推荐动作
- 保留证据与命中关键词
"""

from __future__ import annotations

import re
from typing import Any


TOPIC_KEYWORDS: dict[str, list[str]] = {
    "公安治理": ["公安", "警务", "110", "情指行", "巡防", "公共安全", "视频侦查"],
    "数字政府": ["数字政府", "政务", "一网通办", "一网统管", "政数局", "数据局"],
    "数据治理": ["数据治理", "公共数据", "数据资源", "数据要素", "高质量数据集", "数据共享"],
    "智慧城市": ["智慧城市", "城市大脑", "城市运行", "城市治理", "市域社会治理"],
    "空间数据": [
        "GIS", "地理信息", "测绘", "空间数据", "地理空间", "时空", "时空大数据",
        "实景三维", "数字孪生", "CIM", "自然资源", "国土空间", "地图服务",
        "电子地图", "地址治理", "标准地址", "地理编码", "POI", "AOI",
        "遥感", "点云", "高精地图", "位置智能",
        "OSGeo", "GDAL", "PROJ", "QGIS", "PostGIS", "GeoServer", "MapServer",
    ],
    "AI智能体": ["智能体", "Agent", "大模型", "人工智能", "RAG", "MCP", "生成式AI"],
    "信创与安全": ["信创", "数据安全", "网络安全", "安全评估", "隐私", "合规"],
    "低空与智驾": ["低空经济", "无人机", "自动驾驶", "高精地图", "车路协同"],
}

CUSTOMER_TYPE_KEYWORDS: dict[str, list[str]] = {
    "公安客户": ["公安", "警务", "交警", "派出所", "刑侦"],
    "政数客户": ["政数", "数据局", "大数据局", "行政审批", "政务"],
    "住建城管客户": ["住建", "城管", "城市管理", "住房", "建设"],
    "自然资源客户": ["自然资源", "规划", "测绘", "不动产"],
    "金融客户": ["银行", "保险", "证券", "农信", "农商"],
    "央国企客户": ["集团", "国企", "央企", "投资公司", "数据集团"],
}

HIGH_IMPACT_WORDS = [
    "国家", "国务院", "部委", "规划", "行动", "实施方案", "通知",
    "试点", "示范", "重点工程", "高质量", "统一代码", "公共数据",
]

COMPETITOR_RISK_WORDS = [
    "中标", "入围", "签约", "战略合作", "联合", "发布", "上线", "案例",
]


def build_intelligence_profile(
    *,
    kind: str,
    title: str,
    content: str | None = None,
    source: str | None = None,
    source_url: str | None = None,
    matched_keywords: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成情报解释卡，存入 CrawlerItem.extra_data.agent_profile。"""

    text = f"{title} {content or ''}"
    topics = _match_topics(text)
    customer_types = _match_customer_types(text)
    keywords = _dedupe([*(matched_keywords or []), *_flatten(topics.values())])[:12]
    impact_level = _impact_level(kind, text, topics)
    recommended_action = _recommended_action(kind, impact_level, topics, customer_types)

    evidence = []
    if source:
        evidence.append(f"来源：{source}")
    if source_url:
        evidence.append("已保留原文链接")
    if keywords:
        evidence.append(f"命中关键词：{'、'.join(keywords[:6])}")

    return {
        "kind": kind,
        "topics": list(topics.keys()),
        "topic_hits": topics,
        "customer_types": customer_types,
        "impact_level": impact_level,
        "recommended_action": recommended_action,
        "evidence": evidence,
        "watch_reason": _watch_reason(kind, impact_level, topics, customer_types),
        "raw": dict(extra or {}),
    }


def competitor_event_type(title: str) -> str:
    text = title.lower()
    if any(word in text for word in ["中标", "成交", "入围", "候选人"]):
        return "bidding_win"
    if any(word in text for word in ["案例", "落地", "上线", "应用", "客户"]):
        return "customer_case"
    if any(word in text for word in ["发布", "推出", "新版本", "升级", "产品", "方案"]):
        return "product_update"
    if any(word in text for word in ["合作", "签约", "战略", "协议", "生态", "联合"]):
        return "partnership"
    if any(word in text for word in ["分公司", "区域", "基地", "中心"]):
        return "regional_push"
    if any(word in text for word in ["招聘", "校招", "社招", "人才", "岗位"]):
        return "recruitment"
    if any(word in text for word in ["资质", "专利", "软著", "标准", "认证", "荣誉"]):
        return "qualification"
    return "news"


def contains_keyword(text: str, keyword: str) -> bool:
    """Match Chinese terms by containment and short English terms by token boundary."""

    term = keyword.strip()
    if not text or not term:
        return False

    text_lower = text.lower()
    term_lower = term.lower()
    if _needs_token_boundary(term_lower):
        pattern = rf"(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])"
        return re.search(pattern, text_lower) is not None
    return term_lower in text_lower


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if contains_keyword(text, keyword)]


def _match_topics(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = match_keywords(text, keywords)
        if hits:
            result[topic] = hits
    return result


def _match_customer_types(text: str) -> list[str]:
    result = []
    for customer_type, keywords in CUSTOMER_TYPE_KEYWORDS.items():
        if any(contains_keyword(text, kw) for kw in keywords):
            result.append(customer_type)
    return result


def _impact_level(kind: str, text: str, topics: dict[str, list[str]]) -> str:
    if kind == "competitor" and any(contains_keyword(text, word) for word in COMPETITOR_RISK_WORDS):
        return "medium"
    high_hits = sum(1 for word in HIGH_IMPACT_WORDS if contains_keyword(text, word))
    if kind in {"policy", "bidding"} and (high_hits >= 2 or len(topics) >= 3):
        return "high"
    if high_hits >= 1 or len(topics) >= 2:
        return "medium"
    return "low"


def _recommended_action(
    kind: str,
    impact_level: str,
    topics: dict[str, list[str]],
    customer_types: list[str],
) -> str:
    if kind == "bidding":
        if impact_level == "high":
            return "推荐销售查看"
        if customer_types or topics:
            return "标记观察"
        return "归档观察"
    if kind == "policy":
        if impact_level == "high":
            return "纳入政策解读"
        return "持续观察"
    if kind == "competitor":
        if impact_level in {"high", "medium"}:
            return "提醒区域负责人"
        return "归档监控"
    if kind in {"ai", "news", "industry"}:
        if impact_level in {"high", "medium"}:
            return "补充行业知识库"
        return "归档观察"
    return "归档观察"


def _watch_reason(
    kind: str,
    impact_level: str,
    topics: dict[str, list[str]],
    customer_types: list[str],
) -> str:
    topic_text = "、".join(topics.keys()) or "未命中核心主题"
    customer_text = "、".join(customer_types) or "未识别明确客户类型"
    return f"{kind} 情报，影响等级 {impact_level}；主题：{topic_text}；客户类型：{customer_text}。"


def _flatten(values: list[list[str]]) -> list[str]:
    return [item for sub in values for item in sub]


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _needs_token_boundary(term: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9.+#-]{0,30}", term))
