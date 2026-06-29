"""HTML renderer for bidding express pages."""

from __future__ import annotations

from typing import Any

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



def render_html(express: Any) -> str:
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
                <div class="overview-label">周期标讯总数</div>
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
                <div class="overview-number">{express.period_label}</div>
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
	  <h1>📋 标讯速递</h1>
	  <div class="sub">{express.express_date} · {express.customer_name} · 本次共 {total} 条标讯</div>

  {overview_html}
</div>

{industries_html}

<div class="footer">
  Market 数据采集中心 · 内部资料请勿外传
</div>

</div>
</body>
</html>"""

    return html

