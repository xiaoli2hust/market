"""Default operational seed data for local deployments."""

from __future__ import annotations

import json
from sqlite3 import Connection
from typing import Any


from .crawler_seed_sources import (
    BIDDING_PUBLIC_LIST_SELECTORS,
    COMPETITOR_LIST_SELECTORS,
    DEFAULT_CRAWLER_SOURCES,
    PUBLIC_LIST_SELECTORS,
)

def complete_crawler_source_rules(source: dict[str, Any]) -> dict[str, Any]:
    """Return a source with a real executable crawler rule contract.

    Source rows are allowed to be inactive candidates, but they should not be
    rule-less placeholders. This helper fills missing list/detail selectors for
    public sites and converts legacy browser-only candidates into low-frequency
    public HTML probes. The runtime still stops on login, captcha, 403 or 429.
    """

    completed = dict(source)
    completed["selectors"] = _complete_crawler_selectors(
        category=str(source.get("category") or ""),
        name=str(source.get("name") or ""),
        selectors=source.get("selectors") or {},
    )
    return completed


def _complete_crawler_selectors(
    *,
    category: str,
    name: str,
    selectors: dict[str, Any],
) -> dict[str, Any]:
    completed = dict(selectors or {})
    source_type = str(completed.get("type") or completed.get("source_type") or "official_site")

    if source_type == "api":
        completed.setdefault("risk_level", "authorized_api" if completed.get("protected") else "public_query_api")
        completed.setdefault("rule_profile", "authorized_api_v1" if completed.get("protected") else "public_api_candidate_v1")
        completed.setdefault("rule_status", "executable" if completed.get("protected") else "requires_authorization")
        return completed

    if source_type == "api_post":
        completed.setdefault("risk_level", "public_query_api")
        completed.setdefault("rule_profile", "public_query_api_v1")
        completed.setdefault("rule_status", "executable")
        return completed

    if source_type == "rss":
        completed.setdefault("risk_level", "rss_low")
        completed.setdefault("rule_profile", "rss_feed_v1")
        completed.setdefault("rule_status", "executable")
        return completed

    if source_type == "direct_pages":
        if completed.get("pages"):
            completed.setdefault("risk_level", "medium_js" if category == "competitor" else "medium_static")
            completed.setdefault("rule_profile", "direct_pages_v1")
            completed.setdefault("rule_status", "executable")
            return completed
        completed["original_type"] = "direct_pages_without_pages"
        completed["type"] = "official_site"
        source_type = "official_site"

    if source_type == "browser":
        completed["original_type"] = "browser"
        completed["type"] = "official_site"
        completed["risk_level"] = "medium_js"
        completed.setdefault("rule_profile", "dynamic_public_html_probe_v1")
        completed.setdefault(
            "execution_note",
            "原入口可能动态渲染；当前只执行公开 HTML 低频探测，遇到登录、验证码、403/429 立即冷却。",
        )
        source_type = "official_site"

    if source_type not in {"official_site", "http"}:
        completed.setdefault("risk_level", "normal_public")
        completed.setdefault("rule_profile", "public_html_generic_v1")
        completed.setdefault("rule_status", "executable")
        return completed

    template = _list_rule_template(category, name)
    for key in ("list", "title", "link", "date"):
        completed.setdefault(key, template[key])
    completed.setdefault("risk_level", _default_rule_risk(category, completed))
    completed.setdefault("rule_profile", template["rule_profile"])
    completed.setdefault("rule_status", "executable")
    completed.setdefault("rule_note", template["rule_note"])
    if category == "bidding":
        completed.setdefault("amount_rule_profile", "budget_and_contract_amount_v1")
        completed.setdefault(
            "amount_fields",
            ["预算金额", "最高限价", "中标金额", "成交金额", "合同金额", "采购预算"],
        )
    return completed


def _list_rule_template(category: str, name: str) -> dict[str, Any]:
    if category == "bidding":
        return {
            **BIDDING_PUBLIC_LIST_SELECTORS,
            "rule_profile": "bidding_public_list_v1",
            "rule_note": "按公开公告链接低频抓取，详情页再做关键词、金额和相关性分析。",
        }
    if category == "competitor":
        return {
            **COMPETITOR_LIST_SELECTORS,
            "rule_profile": "competitor_public_list_v1",
            "rule_note": "按官网新闻/产品/案例公开列表低频抓取，抽取竞对动作事件。",
        }
    if category == "ai":
        return {
            **PUBLIC_LIST_SELECTORS,
            "rule_profile": "industry_public_list_v1",
            "rule_note": "按行业知识公开列表低频抓取，过滤 AI Agent 和空间数据主题。",
        }
    if category == "policy":
        return {
            **PUBLIC_LIST_SELECTORS,
            "rule_profile": "policy_public_list_v1",
            "rule_note": "按政策公开栏目低频抓取，按自然年和业务关键词过滤。",
        }
    return {
        **PUBLIC_LIST_SELECTORS,
        "rule_profile": "market_public_list_v1",
        "rule_note": f"{name or '公开来源'}按公开列表低频抓取，命中业务关键词后入库。",
    }


def _default_rule_risk(category: str, selectors: dict[str, Any]) -> str:
    if selectors.get("protected") and selectors.get("type") == "api":
        return "authorized_api"
    if selectors.get("original_type") == "browser":
        return "medium_js"
    if category == "competitor":
        return "medium_js"
    return "normal_public"


CRAWLER_SOURCE_RUNTIME_PATCHES: dict[tuple[str, str], dict[str, Any]] = {
    # 已启用内置源：必须具备真实运行规则，不能只作为页面说明。
    ("policy", "国家数据局"): {
        "url": "https://www.nda.gov.cn/sjj/zwgk/",
        "base_url": "https://www.nda.gov.cn",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "protected": True,
            "scope": "国家数据局政策发布、通知公告、数据要素和公共数据政策",
            "strategy": "按自然年直采重点公开页面，保留与公安/政数/大数据/地址/空间/Agent相关内容",
            "pages": [
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/zcfb/0618/20260618145942270461999_pc.html"},
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/zcfb/0608/20260608172117399715004_pc.html"},
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/tzgg/0428/20260428215540161552208_pc.html"},
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/tzgg/0427/20260427215820802616908_pc.html"},
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/tzgg/0409/20260409092900412958913_pc.html"},
                {"name": "国家数据局", "url": "https://www.nda.gov.cn/sjj/zwgk/tzgg/0213/20260213090050171653926_pc.html"},
            ],
        },
    },
    ("policy", "国家发展改革委政务公开"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "protected": True,
            "scope": "数字经济、数据要素、公共数据和产业政策公开信息",
            "strategy": "低频采集公开列表，按年度和业务关键词过滤",
        },
    },
    ("policy", "自然资源部通知公告"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "protected": True,
            "scope": "自然资源、测绘地理信息、实景三维、空间数据政策通知",
            "strategy": "低频采集公开列表，按年度和业务关键词过滤",
        },
    },
    ("policy", "重庆市人民政府"): {
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "protected": True,
            "scope": "地方数字政府、城市治理、公共数据政策",
            "strategy": "按年度直采重点公开页面，命中业务关键词后入库",
            "pages": [
                {"name": "重庆市人民政府", "url": "https://www.cq.gov.cn/zwgk/zfxxgkml/szfwj/qtgw/202602/t20260212_15440236.html"},
            ],
        },
    },
    ("policy", "北京市政务服务和数据管理局"): {
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "protected": True,
            "scope": "北京政务服务、数据管理、数字政府相关政策",
            "strategy": "按年度直采重点公开页面，命中业务关键词后入库",
            "pages": [
                {"name": "北京市政务服务和数据管理局", "url": "https://zwfwj.beijing.gov.cn/zwgk/2024zcwj/202409/t20240927_3908531.html"},
            ],
        },
    },
    ("news", "自然资源部"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "protected": True,
            "scope": "自然资源、实景三维、空间数据、地理信息相关市场动态",
            "strategy": "低频采集公开列表，按公安/政数/地址/地图/空间/Agent关键词过滤",
        },
    },
    ("news", "福建省数据管理局"): {
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "protected": True,
            "scope": "地方数字化、公共数据、数据要素和政务数据动态",
            "strategy": "按年度直采重点公开页面，命中业务关键词后入库",
            "pages": [
                {"name": "福建省数据管理局", "url": "https://fgw.fujian.gov.cn/ztzl/szfjzt/tzgg/202606/t20260603_7155547.htm"},
            ],
        },
    },
    ("news", "锡林郭勒盟行政公署"): {
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "protected": True,
            "scope": "地方政务数字化、基层治理、公共数据相关动态",
            "strategy": "按年度直采重点公开页面，命中业务关键词后入库",
            "pages": [
                {"name": "锡林郭勒盟行政公署", "url": "https://www.xlgl.gov.cn/xlgl/zw/xsxxgk/fdzdgknr/zcwj/xswj/2026032017203520482/index.html"},
            ],
        },
    },
    ("ai", "机器之心"): {
        "is_active": True,
        "selectors": {
            "type": "http",
            "protected": True,
            "list": "div.article-item, div.article-item-main",
            "title": "a.article-item__title, h4 a, a",
            "link": "a@href",
            "date": "span.time, time",
            "scope": "AI研究、产业应用、模型、Agent和空间智能相关动态",
            "strategy": "低频网页采集，标题必须命中核心AI Agent或空间数据关键词",
        },
    },
    ("ai", "量子位"): {
        "is_active": True,
        "selectors": {
            "type": "http",
            "protected": True,
            "list": "article, div.post-item, div.entry-content",
            "title": "h2 a, h3 a, .entry-title a, a",
            "link": "a@href",
            "date": ".date, time",
            "scope": "AI产品、空间数据行业应用、位置智能和技术趋势动态",
            "strategy": "低频网页采集，标题必须命中核心AI Agent或空间数据关键词",
        },
    },

    # 标讯雷达：授权结构化接口为主，公开源作为补充召回。
    ("bidding", "全国公共资源交易平台"): {
        "url": "https://www.ggzy.gov.cn/",
        "base_url": "https://www.ggzy.gov.cn",
        "is_active": True,
        "selectors": {
            **BIDDING_PUBLIC_LIST_SELECTORS,
            "scope": "全国公共资源交易公开信息，覆盖政府采购、工程建设和交易结果",
            "strategy": "低频采集首页公开公告，先按业务关键词召回，再做相关性评分和金额抽取",
        },
    },
    ("bidding", "北京市公共资源交易服务平台"): {
        "url": "https://ggzyfw.beijing.gov.cn/",
        "base_url": "https://ggzyfw.beijing.gov.cn",
        "is_active": True,
        "selectors": {
            **BIDDING_PUBLIC_LIST_SELECTORS,
            "scope": "北京市公共资源交易、政府采购、工程建设公告公示",
            "strategy": "低频采集公开交易信息，按公安、政数、空间智能、数据治理关键词过滤",
        },
    },
    ("bidding", "浙江省公共资源交易服务平台"): {
        "url": "https://ggzy.zj.gov.cn/",
        "base_url": "https://ggzy.zj.gov.cn",
        "is_active": True,
        "selectors": {
            **BIDDING_PUBLIC_LIST_SELECTORS,
            "scope": "浙江公共资源交易公告、公示和政府采购信息",
            "strategy": "低频采集公开交易信息，重点关注数字政府、自然资源、实景三维和公共数据项目",
        },
    },
    ("bidding", "南方电网供应链统一服务平台"): {
        "url": "https://www.bidding.csg.cn/zbgg/index.jhtml",
        "base_url": "https://www.bidding.csg.cn",
        "is_active": True,
        "selectors": {
            **BIDDING_PUBLIC_LIST_SELECTORS,
            "scope": "南方电网招标采购公告、结果公示等",
            "strategy": "低频采集招标公告，重点关注电力数字化、数据治理、AI和空间智能项目",
        },
    },

    # 竞对监控：先把重点竞对变成真实可运行源。
    ("competitor", "超图软件"): {
        "url": "https://www.supermap.com/zh-cn/a/news/list_3_1.html",
        "base_url": "https://www.supermap.com",
        "is_active": True,
        "selectors": {
            **COMPETITOR_LIST_SELECTORS,
            "scope": "超图官网新闻、案例、产品动态和区域动作",
            "strategy": "低频采集新闻列表，按中标/案例/产品/合作/区域扩张分类研判",
        },
    },
    ("competitor", "吉奥时空/武大吉奥"): {
        "url": "https://www.geostar.com.cn/xwdt/",
        "base_url": "https://www.geostar.com.cn",
        "is_active": True,
        "selectors": {
            **COMPETITOR_LIST_SELECTORS,
            "scope": "武大吉奥/吉奥时空新闻、产品、方案、案例和区域动态",
            "strategy": "低频采集官网新闻和动态，重点监控时空大数据、智慧城市、自然资源和社会治理项目动作",
        },
    },
    ("competitor", "京东与图/京图开放平台"): {
        "url": "https://lbsapi.jd.com/",
        "base_url": "https://lbsapi.jd.com",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "京东地图、地址解析、围栏、路径规划和位置服务能力页",
            "strategy": "直采产品能力页，作为竞对产品动作和方案能力证据，不做高频抓取",
            "pages": [
                {"name": "京图开放平台", "url": "https://lbsapi.jd.com/"},
            ],
        },
    },
    ("competitor", "海致科技"): {
        "url": "https://www.haizhi.com/",
        "base_url": "https://www.haizhi.com",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "海致科技官网、产品、产业级智能体、图计算和行业方案能力页",
            "strategy": "直采官网重点页面，监控产业级智能体、图模融合、公共服务和能源金融场景",
            "pages": [
                {"name": "海致科技官网", "url": "https://www.haizhi.com/"},
            ],
        },
    },
    ("competitor", "易智瑞 GeoScene"): {
        "url": "https://www.geoscene.cn/show-list-952.html",
        "base_url": "https://www.geoscene.cn",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "GeoScene平台、GIS产品、行业解决方案和生态动态",
            "strategy": "直采产品与方案能力页，重点监控国产GIS平台、空间分析、制图和位置智能能力",
            "pages": [
                {
                    "name": "GeoScene平台产品与行业解决方案",
                    "title": "GeoScene平台产品与行业解决方案",
                    "url": "https://www.geoscene.cn/show-list-952.html",
                },
            ],
        },
    },
    ("competitor", "中科星图 GEOVIS"): {
        "url": "https://www.geovis.com.cn/",
        "base_url": "https://www.geovis.com.cn",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "GEOVIS数字地球、空天信息、低空经济、公安警务和时空智能方案",
            "strategy": "直采官网能力页，重点监控低空警务、数字孪生、时空大数据和公共安全方案",
            "pages": [
                {"name": "中科星图官网", "url": "https://www.geovis.com.cn/"},
            ],
        },
    },
    ("competitor", "中地数码 MapGIS"): {
        "url": "https://www.mapgis.com/",
        "base_url": "https://www.mapgis.com",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "MapGIS平台、CIM、时空大数据、自然资源和行业解决方案",
            "strategy": "直采官网能力页，监控GIS平台、CIM、数字孪生和空间数据治理方案变化",
            "pages": [
                {"name": "中地数码 MapGIS官网", "url": "https://www.mapgis.com/"},
            ],
        },
    },
    ("competitor", "航天宏图"): {
        "url": "https://www.piesat.cn/",
        "base_url": "https://www.piesat.cn",
        "is_active": True,
        "selectors": {
            "type": "direct_pages",
            "scope": "遥感、时空大数据、PIE平台、实景三维和行业应用方案",
            "strategy": "直采官网能力页，监控遥感智能、实景三维、数字孪生和时空数据能力",
            "pages": [
                {"name": "航天宏图官网", "url": "https://www.piesat.cn/"},
            ],
        },
    },

    # 政策研判：国家级政策窗口补齐。
    ("policy", "工业和信息化部政策文件"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "工业互联网、人工智能、软件和信息技术服务业政策",
            "strategy": "按自然年和关键词低频采集AI、数据治理、智能体相关政策",
        },
    },
    ("policy", "公安部政府信息公开"): {
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "公安改革、公共安全、科技信息化和社会治理政策动态",
            "strategy": "候选源。当前官网存在访问拦截，默认不自动采集；如需启用，建议先配置稳定公开栏目或人工确认采集入口",
        },
    },
    ("policy", "中央网信办"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "网络数据安全、数字中国、人工智能治理和数据合规政策",
            "strategy": "只保留数据、AI治理、数字中国和安全合规相关内容",
        },
    },
    ("policy", "中国政府网政策文件"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "国务院政策、部门文件和政策解读",
            "strategy": "按自然年和业务关键词筛选国家级政策信号",
        },
    },
    ("policy", "国家能源局政府信息公开"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "能源数字化、智能电网、电力数据和能源AI政策",
            "strategy": "低频采集能源政策公开信息，过滤电力GIS、能源大数据和AI+能源方向",
        },
    },
    ("policy", "国家标准化管理委员会"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "数据、地理信息、人工智能和城市治理相关标准动态",
            "strategy": "低频采集标准动态，用于识别招投标技术门槛和方案合规要求",
        },
    },

    # 市场线索：补行业协会、电力、运营商和行业媒体。
    ("news", "中国信通院"): {
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "数字经济、人工智能、数据治理、产业互联网研究动态",
            "strategy": "候选源。当前站点返回前置校验，默认不自动采集；保留为人工配置栏目或白名单接入对象",
        },
    },
    ("news", "中国地理信息产业协会"): {
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "地理信息产业、GIS、测绘和空间数据行业动态",
            "strategy": "候选源。robots 不允许当前入口采集，默认不自动采集；仅在获得可采集公开入口后启用",
        },
    },
    ("news", "泰伯网"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "地理信息、时空智能、数字孪生和自然资源行业资讯",
            "strategy": "监控行业案例、厂商动态和空间智能趋势",
        },
    },
    ("news", "北极星电力网"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "电力数字化、电网调度、能源AI和智慧能源市场动态",
            "strategy": "只保留电力GIS、能源大数据、智能电网和AI相关内容",
        },
    },
    ("news", "C114通信网"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "运营商、通信行业、算力网络和数字化转型动态",
            "strategy": "跟踪运营商数据、地图、AI和政企市场方向",
        },
    },
    ("news", "国家电网公司新闻"): {
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "电网数字化、能源互联网、智能调度和电力数据动态",
            "strategy": "候选源。当前入口存在 TLS/访问稳定性问题，默认不自动采集；后续可替换为稳定公开栏目",
        },
    },
    ("news", "中国移动新闻中心"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "运营商政企、算力网络、数据要素和AI应用动态",
            "strategy": "监控运营商政企数字化和AI业务方向",
        },
    },
    ("news", "中国联通新闻中心"): {
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "联通政企、数据智能、算力网络和行业应用动态",
            "strategy": "候选源。当前新闻入口不可用，默认不自动采集；后续可配置联通政企或云相关稳定栏目",
        },
    },
    ("news", "中国电信新闻中心"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "电信政企、云网融合、AI、数据和行业数字化动态",
            "strategy": "监控运营商云网、数据治理和AI行业方案",
        },
    },
    ("news", "南方电网新闻中心"): {
        "url": "https://www.csg.cn/xwzx/2026/2026gsyw/",
        "base_url": "https://www.csg.cn/xwzx/2026/2026gsyw/",
        "is_active": False,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "南网数字化、电力数据治理、智能电网和能源服务动态",
            "strategy": "候选源。当前 robots 不允许采集年度新闻栏目，默认不自动采集；如需启用需更换允许采集的公开入口",
        },
    },
    ("news", "国家能源局新闻中心"): {
        "is_active": True,
        "selectors": {
            **PUBLIC_LIST_SELECTORS,
            "scope": "能源政策、能源数字化、智能电网、电力调度和行业建设动态",
            "strategy": "低频采集能源官网公开新闻，过滤电力数字化、智能电网、能源大数据和AI场景",
        },
    },

    # 行业知识：启用低成本 RSS，覆盖 AI Agent 与空间数据两条知识线。
    ("ai", "OpenAI News"): {"is_active": True},
    ("ai", "Google AI Blog"): {"is_active": True},
    ("ai", "Anthropic News"): {"is_active": False},
    ("ai", "Meta AI Blog"): {"is_active": False},
    ("ai", "LangChain Blog"): {"is_active": False},
    ("ai", "LlamaIndex Blog"): {"is_active": False},
    ("ai", "NVIDIA Technical Blog"): {"is_active": False},
    ("ai", "Microsoft AI Blog"): {
        "url": "https://devblogs.microsoft.com/semantic-kernel/feed/",
        "is_active": True,
        "selectors": {
            "type": "rss",
            "scope": "Microsoft Semantic Kernel、Agent框架、工具调用和企业AI工程实践",
            "strategy": "订阅解析，过滤Agent Native、工具调用、企业AI和工程化实践内容",
        },
    },
    ("ai", "Hugging Face Blog"): {"is_active": True},
    ("ai", "arXiv cs.AI"): {"is_active": True},
    ("ai", "arXiv cs.CL"): {"is_active": True},
    ("ai", "OGC News"): {"is_active": False},
    ("ai", "Esri Blog"): {"is_active": False},
    ("ai", "OSGeo Foundation News"): {
        "is_active": True,
        "selectors": {
            "type": "rss",
            "scope": "开源 GIS、GDAL/PROJ、地理空间软件生态、空间数据工程和开源标准动态",
            "strategy": "行业知识源：订阅解析，过滤空间数据、GIS平台、地理空间软件和AI+地理空间工程实践",
            "risk_level": "rss_low",
            "knowledge_domain": "spatial",
        },
    },
    ("ai", "QGIS.org Blog"): {"is_active": True},
    ("ai", "OpenStreetMap Blog"): {"is_active": True},
    ("ai", "GeoServer Blog"): {"is_active": True},
    ("ai", "GeoTools Blog"): {"is_active": True},
}


def ensure_default_crawler_sources_sqlite(conn: Connection) -> None:
    """Seed default crawler source rows into SQLite without overwriting edits."""

    for source in DEFAULT_CRAWLER_SOURCES:
        source = complete_crawler_source_rules(source)
        conn.execute(
            """
            INSERT INTO crawler_sources (category, name, url, base_url, selectors, is_active)
            SELECT ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM crawler_sources WHERE category = ? AND name = ?
            )
            """,
            (
                source["category"],
                source["name"],
                source["url"],
                source.get("base_url"),
                json.dumps(source["selectors"], ensure_ascii=False),
                1 if source.get("is_active", True) else 0,
                source["category"],
                source["name"],
            ),
        )

    for (category, name), patch in CRAWLER_SOURCE_RUNTIME_PATCHES.items():
        fields: list[str] = []
        values: list[Any] = []
        for field in ("url", "base_url", "is_active"):
            if field not in patch:
                continue
            fields.append(f"{field} = ?")
            values.append(1 if field == "is_active" and patch[field] else patch[field])
        if "selectors" in patch:
            fields.append("selectors = ?")
            merged_patch = complete_crawler_source_rules({
                "category": category,
                "name": name,
                "selectors": patch["selectors"],
            })
            values.append(json.dumps(merged_patch["selectors"], ensure_ascii=False))
        if not fields:
            continue
        conn.execute(
            f"""
            UPDATE crawler_sources
            SET {", ".join(fields)}
            WHERE category = ? AND name = ?
            """,
            [*values, category, name],
        )

    rows = conn.execute(
        "SELECT id, category, name, selectors FROM crawler_sources"
    ).fetchall()
    for row in rows:
        row_id, category, name, raw_selectors = row
        try:
            selectors = json.loads(raw_selectors or "{}")
        except json.JSONDecodeError:
            selectors = {}
        completed = complete_crawler_source_rules({
            "category": category,
            "name": name,
            "selectors": selectors,
        })["selectors"]
        if completed != selectors:
            conn.execute(
                "UPDATE crawler_sources SET selectors = ? WHERE id = ?",
                (json.dumps(completed, ensure_ascii=False), row_id),
            )
