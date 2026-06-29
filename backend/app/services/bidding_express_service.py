"""结构化标讯整合服务 v2 — 按行业分组 + 关键词聚合 + 完整信息提取。"""

from __future__ import annotations

import logging
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_JIANYU_API = "https://customer.jianyu360.com/private/keydatademo/{key}"

# 行业分类规则
INDUSTRY_KEYWORDS = {
    '公安': ['公安', '警务', '110', '情指行', '反诈', '接处警', '智慧公安', '交警', '治安', '刑侦', '网安'],
    '政数': ['政数', '数字政府', '一网统管', '一网通办', '城市大脑', '智慧城市', '政务', '行政审批', '公共服务'],
    '电力': ['电力', '电网', '能源', '供电', '发电', '配电', '用电', '新能源', '光伏', '风电'],
    '自然资源': ['自然资源', '测绘', '地理信息', '实景三维', 'CIM', '国土', '规划', '地理实体', '不动产登记', '土地利用'],
    '企业服务': ['数据', '信息化', '系统集成', '软件', '平台', '云计算', '大数据', '人工智能', '物联网'],
}

# 关键词聚合规则（每个行业内的关键词分组）
KEYWORD_GROUPS = {
    '公安': {
        '情指行': ['情指行', '情报指挥', '指挥调度', '合成作战'],
        '反诈': ['反诈', '反诈骗', '预警', '劝阻'],
        '110 接处警': ['110', '接处警', '报警', '处警'],
        '智慧警务': ['智慧公安', '智慧警务', '公安大数据', '警务云'],
        '交通管理': ['交警', '交通管理', '车辆管理', '驾驶证'],
    },
    '政数': {
        '一网通办': ['一网通办', '政务服务', '行政审批', '公共服务'],
        '一网统管': ['一网统管', '城市运行', '社会治理', '网格化'],
        '城市大脑': ['城市大脑', '智慧城市', '智能中枢'],
        '数据共享': ['数据共享', '数据开放', '数据交换'],
    },
    '自然资源': {
        '实景三维': ['实景三维', '三维建模', '倾斜摄影', '点云'],
        '地理信息': ['地理信息', 'GIS', '地图', '测绘'],
        'CIM 平台': ['CIM', '城市信息模型', 'BIM'],
        '国土规划': ['国土', '规划', '土地利用', '不动产登记'],
    },
    '企业服务': {
        '数据治理': ['数据治理', '数据质量', '数据标准'],
        '系统集成': ['系统集成', '信息化建设', '平台建设'],
        '云计算': ['云计算', '云服务', '云安全'],
        '人工智能': ['人工智能', 'AI', '机器学习', '大模型'],
    },
}


@dataclass
class BiddingItem:
    """单条标讯（完整信息）。"""
    title: str
    buyer: str  # 采购单位
    buyer_contact: str  # 联系人
    buyer_phone: str  # 联系电话
    budget: str  # 预算金额（万元）
    bid_amount: str  # 中标金额（万元）
    winner: str  # 中标单位
    pub_time: str  # 发布时间
    subtype: str  # 公告类型（招标/中标/成交...）
    province: str
    city: str
    keywords: str
    detail: str  # 项目详情/摘要
    project_name: str  # 项目名称
    project_code: str  # 项目编号
    deadline: str  # 开标日期/截止时间
    href: str  # 详情链接
    industry: str = ''  # 行业
    keyword_group: str = ''  # 关键词分组
    priority_score: int = 0  # 优先级评分（0-100）


@dataclass
class KeywordGroup:
    """一个关键词分组。"""
    name: str
    items: list[BiddingItem] = field(default_factory=list)


@dataclass
class IndustryGroup:
    """一个行业分组。"""
    name: str
    keyword_groups: list[KeywordGroup] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(g.items) for g in self.keyword_groups)


@dataclass
class BiddingExpress:
    """整合后的标讯速递。"""
    express_date: str
    period: str
    period_label: str
    period_start: str | None
    period_end: str | None
    customer_name: str
    source_total: int
    total: int
    industries: list[IndustryGroup]
    high_value_items: list[BiddingItem]  # 高金额标讯（>100 万）

    @property
    def priority_items(self) -> list[BiddingItem]:
        """需要优先关注的标讯。"""

        return [
            item
            for industry in self.industries
            for group in industry.keyword_groups
            for item in group.items
            if item.priority_score >= 70
        ]


def _parse_amount(amount_str: str) -> float:
    """解析金额字符串为数值（万元）。"""
    if not amount_str:
        return 0.0
    try:
        return float(amount_str)
    except (TypeError, ValueError):
        return 0.0


def _subtype_priority(subtype: str) -> int:
    """公告类型优先级：招标公示 > 中标成交 > 意向其他。"""
    priority_map = {
        '招标': 100,
        '公示': 90,
        '公告': 80,
        '中标': 70,
        '成交': 60,
        '竞谈': 50,
        '询价': 40,
        '单一': 30,
        '采购意向': 20,
        '意向': 20,
        '变更': 10,
        '废标': 5,
        '流标': 5,
    }
    for key, score in priority_map.items():
        if key in subtype:
            return score
    return 0


def classify_industry(keywords: str, title: str, buyer: str) -> str:
    """分类行业。"""
    text = f"{keywords} {title} {buyer}".lower()

    for industry, kws in INDUSTRY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return industry
    return '其他'


def classify_keyword_group(industry: str, keywords: str, title: str) -> str:
    """分类关键词分组。"""
    text = f"{keywords} {title}".lower()

    if industry in KEYWORD_GROUPS:
        for group_name, kws in KEYWORD_GROUPS[industry].items():
            if any(kw in text for kw in kws):
                return group_name

    # 默认用第一个关键词
    if keywords:
        return keywords.split(',')[0].strip()
    return '其他'


def calculate_priority_score(item: BiddingItem) -> int:
    """计算标讯优先级评分（0-100）。"""
    score = 0

    # 1. 公告类型优先级（40 分）
    subtype_priority_map = {
        '招标': 40,
        '公示': 35,
        '公告': 30,
        '中标': 25,
        '成交': 25,
        '竞谈': 20,
        '询价': 15,
        '单一': 10,
        '采购意向': 10,
        '意向': 10,
        '变更': 5,
        '废标': 0,
        '流标': 0,
    }
    for key, pts in subtype_priority_map.items():
        if key in item.subtype:
            score += pts
            break

    # 2. 金额加分（30 分）
    amount = max(_parse_amount(item.budget), _parse_amount(item.bid_amount))
    if amount > 500:
        score += 30
    elif amount > 100:
        score += 25
    elif amount > 50:
        score += 20
    elif amount > 10:
        score += 10

    # 3. 关键词匹配度（20 分）
    keyword_count = len([kw for kw in item.keywords.split(',') if kw.strip()]) if item.keywords else 0
    if keyword_count >= 4:
        score += 20
    elif keyword_count >= 3:
        score += 15
    elif keyword_count >= 2:
        score += 10
    elif keyword_count >= 1:
        score += 5

    # 4. 采购单位质量（10 分）
    buyer = item.buyer.lower()
    if any(kw in buyer for kw in ['公安局', '公安厅', '公安厅', '政府', '政务']):
        score += 10
    elif any(kw in buyer for kw in ['银行', '电信', '联通', '移动', '能源']):
        score += 8
    elif any(kw in buyer for kw in ['有限', '股份', '公司']):
        score += 5

    return min(score, 100)


def fetch_bidding_data(api_key: str) -> tuple[list[dict], str]:
    """调用结构化标讯 API 获取原始数据。"""
    resp = httpx.get(
        _JIANYU_API.format(key=api_key),
        params={"type": "private"},
        timeout=30,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    if "err" in data and data["err"]:
        raise RuntimeError(f"API 错误：{data['err']}")
    return data.get("data", []), data.get("customername", "")


def build_express(api_key: str, express_date: str | None = None, period: str = "week") -> BiddingExpress:
    """获取数据并整合成标讯速递。"""
    raw_items, customer_name = fetch_bidding_data(api_key)

    if not express_date:
        express_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    anchor_date = _parse_date_value(express_date) or datetime.now(timezone.utc).date()
    period = _normalize_period(period)
    period_start, period_end = _period_window(anchor_date, period)

    # 转换为 BiddingItem。API 侧已经按账号规则返回结构化标讯，这里不再写死日期窗口。
    items: list[BiddingItem] = []
    for raw in raw_items:
        pub_time = raw.get("publishtime", "")

        title = raw.get("title", "").strip()
        if not title:
            pkgs = raw.get("com_package", [])
            title = pkgs[0].get("name", "").strip() if pkgs else ""
        if not title:
            continue

        # 行业分类
        keywords = raw.get("s_matchkey", "")
        buyer = raw.get("buyer", "")
        industry = classify_industry(keywords, title, buyer)
        keyword_group = classify_keyword_group(industry, keywords, title)

        item = BiddingItem(
            title=title,
            buyer=buyer,
            buyer_contact=raw.get("buyerperson", ""),
            buyer_phone=raw.get("buyertel", ""),
            budget=raw.get("bidamount", ""),
            bid_amount=raw.get("win_bid_amount", ""),
            winner=raw.get("winner", ""),
            pub_time=pub_time,
            subtype=raw.get("subtype", "其它"),
            province=raw.get("area", ""),
            city=raw.get("city", ""),
            keywords=keywords,
            detail=raw.get("detail", ""),
            project_name=raw.get("projectname", ""),
            project_code=raw.get("projectcode", ""),
            deadline=raw.get("deadline", ""),
            href=raw.get("s_jyhref", raw.get("href", "")),
            industry=industry,
            keyword_group=keyword_group,
            priority_score=calculate_priority_score(
                BiddingItem(title=title, buyer=buyer, buyer_contact="", buyer_phone="",
                           budget=raw.get("bidamount", ""), bid_amount=raw.get("win_bid_amount", ""),
                           winner=raw.get("winner", ""), pub_time=pub_time,
                           subtype=raw.get("subtype", "其它"), province=raw.get("area", ""),
                           city=raw.get("city", ""), keywords=keywords, detail="",
                           project_name="", project_code="", deadline="", href="",
                           industry=industry, keyword_group=keyword_group)
            ),
        )
        if period == "all" or _is_in_period(pub_time, period_start, period_end):
            items.append(item)

    # 按行业分组
    industry_map: dict[str, IndustryGroup] = {}
    for item in items:
        if item.industry not in industry_map:
            industry_map[item.industry] = IndustryGroup(name=item.industry)

        # 找或创建关键词分组
        kg_map = {kg.name: kg for kg in industry_map[item.industry].keyword_groups}
        if item.keyword_group not in kg_map:
            kg_map[item.keyword_group] = KeywordGroup(name=item.keyword_group)
            industry_map[item.industry].keyword_groups.append(kg_map[item.keyword_group])

        kg_map[item.keyword_group].items.append(item)

    # 排序：行业按数量降序，关键词分组按公告类型优先级+数量排序
    industries = sorted(industry_map.values(), key=lambda x: -x.total)
    for ind in industries:
        ind.keyword_groups.sort(key=lambda x: (-_subtype_priority(x.items[0].subtype) if x.items else 0, -len(x.items)))
        # 每个关键词分组内按公告类型优先级排序
        for kg in ind.keyword_groups:
            kg.items.sort(key=lambda x: (-_subtype_priority(x.subtype), x.pub_time, -_parse_amount(x.budget)))

    # 高金额标讯（>100 万）
    high_value = sorted(
        [item for item in items if _parse_amount(item.budget) > 100 or _parse_amount(item.bid_amount) > 100],
        key=lambda x: -max(_parse_amount(x.budget), _parse_amount(x.bid_amount))
    )

    return BiddingExpress(
        express_date=express_date,
        period=period,
        period_label=_format_period_label(period_start, period_end, period),
        period_start=period_start.isoformat() if period_start else None,
        period_end=period_end.isoformat() if period_end else None,
        customer_name=customer_name,
        source_total=len(raw_items),
        total=len(items),
        industries=industries,
        high_value_items=high_value,
    )


from .bidding_express_render import render_html


def _normalize_period(period: str | None) -> str:
    value = (period or "week").strip().lower()
    if value in {"day", "today"}:
        return "day"
    if value in {"week", "weekly"}:
        return "week"
    if value in {"month", "monthly"}:
        return "month"
    if value in {"all", "all_time"}:
        return "all"
    return "week"


def _period_window(anchor: date, period: str) -> tuple[date | None, date | None]:
    if period == "day":
        return anchor, anchor
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        _, last_day = calendar.monthrange(anchor.year, anchor.month)
        return date(anchor.year, anchor.month, 1), date(anchor.year, anchor.month, last_day)
    return None, None


def _is_in_period(value: Any, start: date | None, end: date | None) -> bool:
    if start is None or end is None:
        return True
    pub_date = _parse_date_value(value)
    if pub_date is None:
        return False
    return start <= pub_date <= end


def _parse_date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    patterns = [
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        r"(20\d{2})/(\d{1,2})/(\d{1,2})",
        r"(20\d{2})\.(\d{1,2})\.(\d{1,2})",
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            year, month, day = (int(part) for part in match.groups())
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _format_period_label(start: date | None, end: date | None, period: str) -> str:
    if period == "all" or not start or not end:
        return "全部"
    start_label = start.strftime("%m.%d")
    end_label = end.strftime("%m.%d")
    if start == end:
        return start_label
    return f"{start_label}-{end_label}"


def _period_label(items: list[BiddingItem], fallback: str) -> str:
    dates = sorted(
        {
            item.pub_time[:10]
            for item in items
            if item.pub_time and re.match(r"20\d{2}-\d{2}-\d{2}", item.pub_time[:10])
        }
    )
    if not dates:
        return fallback
    start = dates[0][5:].replace("-", ".")
    end = dates[-1][5:].replace("-", ".")
    return start if start == end else f"{start}-{end}"
