"""剑鱼标讯整合服务 v2 — 按行业分组 + 关键词聚合 + 完整信息提取。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    customer_name: str
    total: int
    industries: list[IndustryGroup]
    high_value_items: list[BiddingItem]  # 高金额标讯（>100 万）


def _parse_amount(amount_str: str) -> float:
    """解析金额字符串为数值（万元）。"""
    if not amount_str:
        return 0.0
    try:
        return float(amount_str)
    except:
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
    """调用剑鱼 API 获取原始数据。"""
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


def build_express(api_key: str, express_date: str | None = None) -> BiddingExpress:
    """获取数据并整合成标讯速递。"""
    raw_items, customer_name = fetch_bidding_data(api_key)

    if not express_date:
        express_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 转换为 BiddingItem，过滤 6 月 15-16 日数据
    items: list[BiddingItem] = []
    for raw in raw_items:
        pub_time = raw.get("publishtime", "")
        # 只保留 6 月 15-16 日数据
        if not pub_time.startswith("2026-06"):
            continue
        day = int(pub_time.split("-")[2]) if pub_time else 0
        if day < 15 or day > 16:
            continue

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
        customer_name=customer_name,
        total=len(items),
        industries=industries,
        high_value_items=high_value,
    )


def render_html(express: BiddingExpress) -> str:
    """渲染标讯速递 HTML（行业卡片 + 全宽布局）。"""

    # 本周总览统计
    total = express.total
    industry_stats = "、".join(f"{ind.name} {ind.total}条" for ind in express.industries if ind.total > 0)

    # 统计公告类型
    subtype_dist = {}
    for ind in express.industries:
        for kg in ind.keyword_groups:
            for item in kg.items:
                subtype_dist[item.subtype] = subtype_dist.get(item.subtype, 0) + 1
    subtype_stats = "、".join(f"{k} {v}条" for k, v in sorted(subtype_dist.items(), key=lambda x: -x[1])[:6])

    # 统计关键词
    all_keywords = set()
    for ind in express.industries:
        for kg in ind.keyword_groups:
            all_keywords.add(kg.name)
    keyword_stats = "、".join(sorted(all_keywords)[:15])

    overview_html = f"""
        <div class="overview-grid">
            <div class="overview-card">
                <div class="overview-number">{total}</div>
                <div class="overview-label">本周标讯总数</div>
            </div>
            <div class="overview-card">
                <div class="overview-number">{len(express.industries)}</div>
                <div class="overview-label">覆盖行业</div>
            </div>
            <div class="overview-card">
                <div class="overview-number">{len(all_keywords)}</div>
                <div class="overview-label">关键词分组</div>
            </div>
            <div class="overview-card">
                <div class="overview-number">6.15-6.16</div>
                <div class="overview-label">统计周期</div>
            </div>
        </div>
        <div class="overview-detail">
            <div><strong>行业分布：</strong>{industry_stats}</div>
            <div><strong>公告类型：</strong>{subtype_stats}</div>
            <div><strong>关键词：</strong>{keyword_stats}</div>
        </div>
    """

    # 行业卡片
    industries_html = '<div class="industries-grid">'
    for ind in express.industries:
        industries_html += f"""
            <div class="industry-card">
                <div class="industry-header">
                    <h2>🏢 {ind.name}</h2>
                    <span class="industry-count">{ind.total} 条</span>
                </div>
        """

        for kg in ind.keyword_groups:
            # 按公告类型分组
            subtype_groups = {}
            for item in kg.items:
                if item.subtype not in subtype_groups:
                    subtype_groups[item.subtype] = []
                subtype_groups[item.subtype].append(item)

            # 按优先级排序公告类型
            sorted_subtypes = sorted(subtype_groups.keys(), key=lambda x: -_subtype_priority(x))

            industries_html += f"""
                <div class="keyword-section">
                    <h3>🔑 {kg.name} <span class="count">{len(kg.items)} 条</span></h3>
            """

            for subtype in sorted_subtypes:
                items = subtype_groups[subtype]
                # 按优先级评分排序
                items.sort(key=lambda x: -x.priority_score)
                industries_html += f"""
                    <div class="subtype-group">
                        <div class="subtype-header">
                            <span class="type-badge {subtype}">{subtype}</span>
                            <span class="count">{len(items)} 条</span>
                        </div>
                        <div class="items-list">
                """

                for item in items:
                    amount = _parse_amount(item.budget)
                    amount_html = f'<span class="amount">{amount:.0f}万</span>' if amount > 0 else ''
                    # 提取关键词标记
                    keyword_tags = ""
                    if item.keywords:
                        tags = [kw.strip() for kw in item.keywords.split(",") if kw.strip()][:4]
                        keyword_tags = " ".join(f'<span class="kw-tag">{t}</span>' for t in tags)

                    # 提取核心事项（从标题中提取动作）
                    if '招标' in item.subtype:
                        action_desc = '正在招标'
                    elif '中标' in item.subtype or '成交' in item.subtype:
                        action_desc = '已开标'
                    elif '意向' in item.subtype:
                        action_desc = '采购意向'
                    else:
                        action_desc = item.subtype

                    industries_html += f"""
                        <div class="bidding-item" data-score="{item.priority_score}">
                            <div class="item-head">
                                <h4 class="item-title">{item.title}</h4>
                                <div class="item-score-badge">
                                    {amount_html}
                                    <span class="score-badge score-{item.priority_score // 10 * 10}">{item.priority_score}分</span>
                                </div>
                            </div>
                            <div class="item-meta">
                                <span class="meta-item">🏢 {item.buyer}</span>
                                <span class="meta-item">📅 {item.pub_time}</span>
                                <span class="type-badge {item.subtype}">{action_desc}</span>
                            </div>
                            {f'<div class="item-keywords">{keyword_tags}</div>' if keyword_tags else ''}
                            {f'<div class="item-winner"><strong>中标：</strong>{item.winner}</div>' if item.winner else ''}
                            {f'<div class="item-amount-detail"><strong>预算：</strong>{amount:.1f}万元</div>' if amount > 0 else ''}
                        </div>
                    """

                industries_html += """
                        </div>
                    </div>
                """

            industries_html += "</div>"

        industries_html += "</div>"

    industries_html += "</div>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>标讯速递 {express.express_date}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Microsoft YaHei", "Segoe UI", sans-serif;
    background: #f5f7fa;
    color: #333;
    padding: 24px;
  }}
  .container {{
    max-width: 1400px;
    margin: 0 auto;
  }}

  .header {{
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white;
    padding: 32px;
    border-radius: 12px;
    margin-bottom: 24px;
  }}
  .header h1 {{
    font-size: 28px;
    margin-bottom: 8px;
  }}
  .header .sub {{
    font-size: 15px;
    opacity: 0.9;
    margin-bottom: 24px;
  }}

  .overview-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }}
  .overview-card {{
    background: rgba(255,255,255,0.15);
    padding: 20px;
    border-radius: 10px;
    text-align: center;
  }}
  .overview-number {{
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  .overview-label {{
    font-size: 13px;
    opacity: 0.85;
  }}

  .overview-detail {{
    background: rgba(255,255,255,0.1);
    padding: 16px 20px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.8;
  }}
  .overview-detail div {{
    margin-bottom: 4px;
  }}
  .overview-detail strong {{
    color: #ffd54f;
  }}

  .industries-grid {{
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}

  .industry-card {{
    background: white;
    border-radius: 10px;
    padding: 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }}
  .industry-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e8f0fe;
  }}
  .industry-header h2 {{
    font-size: 17px;
    color: #1a73e8;
  }}
  .industry-count {{
    background: #e3f2fd;
    color: #1565c0;
    padding: 3px 12px;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 600;
  }}

  .keyword-section {{
    margin-bottom: 14px;
  }}
  .keyword-section h3 {{
    font-size: 14px;
    color: #555;
    margin-bottom: 10px;
    padding: 7px 12px;
    background: #f8f9fa;
    border-radius: 6px;
  }}
  .keyword-section h3 .count {{
    font-size: 12px;
    color: #999;
    font-weight: normal;
  }}

  .subtype-group {{
    margin-bottom: 10px;
  }}
  .subtype-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }}
  .type-badge {{
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 600;
  }}
  .type-badge.招标 {{ background: #ffebee; color: #c62828; }}
  .type-badge.中标 {{ background: #e8f5e9; color: #2e7d32; }}
  .type-badge.成交 {{ background: #e8f5e9; color: #2e7d32; }}
  .type-badge.采购意向 {{ background: #f3e5f5; color: #7b1fa2; }}
  .type-badge.竞谈 {{ background: #fff3e0; color: #e65100; }}
  .type-badge.询价 {{ background: #e0f2f1; color: #00695c; }}
  .type-badge.变更 {{ background: #fff8e1; color: #f57f17; }}
  .type-badge.废标 {{ background: #ffebee; color: #b71c1c; }}
  .type-badge.流标 {{ background: #ffebee; color: #b71c1c; }}
  .type-badge.预告 {{ background: #e8eaf6; color: #283593; }}
  .type-badge.单一 {{ background: #f1f8e9; color: #33691e; }}

  .subtype-header .count {{
    font-size: 11px;
    color: #999;
  }}

  .items-list {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}

  .bidding-item {{
    background: #fafbfc;
    border: 1px solid #e8e8e8;
    border-radius: 6px;
    padding: 10px 12px;
    transition: all 0.2s;
  }}
  .bidding-item:hover {{
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    border-color: #1a73e8;
  }}

  .item-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .item-title {{
    font-size: 13px;
    font-weight: 600;
    color: #222;
    line-height: 1.4;
    flex: 1;
  }}
  .item-score-badge {{
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
  }}
  .amount {{
    font-size: 12px;
    color: #e65100;
    font-weight: 700;
    white-space: nowrap;
  }}
  .score-badge {{
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 8px;
    font-weight: 600;
    color: white;
  }}
  .score-80 {{ background: #c62828; }}
  .score-70 {{ background: #e65100; }}
  .score-60 {{ background: #f57f17; }}
  .score-50 {{ background: #1565c0; }}
  .score-40 {{ background: #2e7d32; }}
  .score-30 {{ background: #00695c; }}
  .score-20 {{ background: #6a1b9a; }}
  .score-10 {{ background: #424242; }}
  .score-0 {{ background: #9e9e9e; }}

  .item-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 12px;
    color: #555;
    margin-bottom: 6px;
  }}
  .meta-item {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }}

  .item-keywords {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 6px;
  }}
  .kw-tag {{
    font-size: 10px;
    padding: 2px 8px;
    background: #e3f2fd;
    color: #1565c0;
    border-radius: 10px;
    font-weight: 500;
  }}

  .item-winner {{
    font-size: 12px;
    color: #2e7d32;
    padding: 6px 10px;
    background: #e8f5e9;
    border-radius: 4px;
    margin-top: 6px;
  }}
  .item-winner strong {{
    color: #1b5e20;
  }}

  .item-amount-detail {{
    font-size: 12px;
    color: #e65100;
    padding: 4px 0;
    margin-top: 4px;
  }}
  .item-amount-detail strong {{
    color: #bf360c;
  }}

  .footer {{
    text-align: center;
    font-size: 12px;
    color: #999;
    padding: 30px 20px 10px;
  }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>📋 今日标讯速递</h1>
  <div class="sub">{express.express_date} · {express.customer_name} · 今日共 {total} 条标讯</div>

  {overview_html}
</div>

{industries_html}

<div class="footer">
  营销数据驾驶舱 · 内部资料请勿外传
</div>

</div>
</body>
</html>"""

    return html
