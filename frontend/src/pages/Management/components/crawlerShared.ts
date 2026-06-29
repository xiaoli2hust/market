import type { CrawlerSourceItem } from '@/services/api';

export const CRAWLER_MESSAGE_KEY = 'crawler-run-status';

export const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  bidding: { label: '标讯雷达', color: '#f5222d' },
  policy: { label: '政策研判', color: '#13c2c2' },
  news: { label: '市场线索', color: '#1890ff' },
  competitor: { label: '竞对监控', color: '#fa8c16' },
  ai: { label: '行业知识', color: '#722ed1' },
};

export const SOURCE_CATEGORY_ORDER = ['bidding', 'policy', 'news', 'competitor', 'ai'];

export const TARGET_SOURCE_CATEGORY_OPTIONS = SOURCE_CATEGORY_ORDER
  .map((value) => ({ value, label: CATEGORY_LABELS[value].label }));

export const BIDDING_KEYWORDS_CONFIG = {
  search: {
    label: '搜索关键词',
    desc: '在结构化标讯数据源检索时使用的关键词（精选高频词）',
    toG_公安: ['智慧公安','智慧警务','公安局信息化','情指行','110接处警','视频监控 公安','雪亮工程','公安大数据','警用地理','天网工程'],
    toG_政数: ['数字政府','一网统管','一网通办','智慧城市','城市大脑','政数局','数据局','数字孪生','实景三维','自然资源信息化','时空大数据'],
    toB_零售: ['售后服务 信息化','上门服务 系统','物流配送 系统','零售连锁 数字化','工单管理'],
    toB_金融: ['银行 数字化转型','银行 数据治理','保险 反欺诈','农信社 信息化','金融 风控 大数据'],
    toB_智驾: ['自动驾驶 地图','高精地图','智能驾驶 数据','车路协同','智驾 采集'],
  },
  scoring: {
    label: '评分关键词',
    desc: '采集到标讯后，用于匹配评分的业务关键词（全面覆盖）',
    toG_公安: '实时警情定位、网格绘制、网格化管理、反诈、一张图、情指行、地址画像、地址服务、地址治理、地址标准化、地址解析、地址匹配、地理编码、地址库、标准地址、一标三实、二维码门牌、地址采集、地址清洗、地址关联、地址可视化、地址大数据、地址核采、地址核验、地址引擎、警情定位、110、接处警、智能体、AGENT、PGIS、警用GIS、合成作战、指挥调度、视频侦查、智能研判、预警、布控',
    toG_政数: '时空大数据、地址、标准地址、地址核采、地址采集、地址治理、数据更新、数据运营、城市大脑、市域社会治理、一网统管、一网通办、二维码门牌、一标三实、实有人口、BIM、实景三维、分层分户、地理实体、数字孪生平台、电子地图、二标四实、人口地址、数据采集、智能体、AGENT、数字孪生、CIM、网格化管理、社会治理、政务数据、数据共享',
    toB_零售: '配送调度、智能派单、履约管理、售后管理、上门服务管理、工单管理、服务时效、服务覆盖、网点管理、工程师管理、地址标准化、地址治理、非标地址、地址解析、地址校验、地理编码、空间数据治理、区域运营、网格化管理、业务可视化、经营一张图、运营态势感知、门店管理、会员管理、物流配送、供应链管理、路径规划',
    toB_金融: '地址标准化、地址大数据、地址核验、地址清洗、地址匹配、语义地址、金融地图、位置智能、GIS服务、地图API、轨迹纠偏、逆地理编码、定位服务、路径规划、企业大数据、时空大数据、位置大数据、数据融合、数据治理、企业画像、数字孪生、AOI地图数据、线下巡检、信息稽核、经营场所验证、贷后监控、风险识别、反欺诈调查、网点选址、商圈分析、客户分布、精准营销、网点效能评价、移动展业、客户画像、地图可视化、数据可视化、私有化部署、API接口',
    toB_智驾: '合规采集、数据采集、道路信息采集、采集司机、采集管理、采集备案、跟车采集、合规安全员、数据标注、点云建图、高精地图制作、高精地图建图、高精地图制图、智驾地图制作、合规云、数据合规、合规托管、合规服务、合规咨询、保密机房、数据脱敏脱密、数据安全保护、点云、激光雷达、仿真测试',
  },
};

export const DIRECTION_META: Record<string, { label: string; color: string; icon: string }> = {
  toG_公安: { label: 'toG · 公安', color: '#f5222d', icon: '🚔' },
  toG_政数: { label: 'toG · 政数', color: '#1890ff', icon: '🏛️' },
  toB_零售: { label: 'toB · 零售', color: '#fa8c16', icon: '🛒' },
  toB_金融: { label: 'toB · 金融', color: '#52c41a', icon: '🏦' },
  toB_智驾: { label: 'toB · 智驾', color: '#722ed1', icon: '🚗' },
};

export const DIRECTION_KEYS = Object.keys(DIRECTION_META);
export const splitKeywordText = (text: string) => text.split(/[,，、]/).map(s => s.trim()).filter(Boolean);
export const KEYWORD_CATEGORY_ORDER = ['policy', 'news', 'competitor', 'ai'];

export const SOURCE_TYPE_OPTIONS = [
  { value: 'official_site', label: '官网/网页' },
  { value: 'rss', label: '订阅' },
  { value: 'api_post', label: '接口（候选）' },
  { value: 'browser', label: '渲染页' },
];

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  api: '接口',
  api_post: '接口',
  http: '网页',
  direct_pages: '直采页',
  official_site: '官网/网页',
  rss: '订阅',
  browser: '渲染页',
};

export const inferRiskLevelBySourceType = (sourceType?: string, category?: string) => {
  if (sourceType === 'api') return 'authorized_api';
  if (sourceType === 'api_post') return 'public_query_api';
  if (sourceType === 'rss') return 'rss_low';
  if (sourceType === 'browser') return 'high_js';
  if (sourceType === 'direct_pages') return category === 'competitor' ? 'medium_js' : 'medium_static';
  return 'normal_public';
};

export const SOURCE_CAPABILITY_META: Record<string, { label: string; color: string }> = {
  ready: { label: '已接入', color: 'green' },
  candidate: { label: '候选源', color: 'blue' },
  needs_selectors: { label: '缺解析规则', color: 'orange' },
  not_connected: { label: '未接入', color: 'red' },
};

export const SOURCE_RUNTIME_META: Record<string, { label: string; color: string }> = {
  pending: { label: '未运行', color: 'default' },
  healthy: { label: '健康', color: 'green' },
  empty: { label: '空跑', color: 'gold' },
  blocked: { label: '受限', color: 'orange' },
  cooling: { label: '冷却中', color: 'purple' },
  error: { label: '异常', color: 'red' },
  skipped: { label: '已跳过', color: 'default' },
};

export const SOURCE_RISK_META: Record<string, { label: string; color: string }> = {
  authorized_api: { label: '授权接口', color: 'green' },
  public_query_api: { label: '公开接口', color: 'cyan' },
  rss_low: { label: '订阅低风险', color: 'blue' },
  normal_public: { label: '普通公开页', color: 'default' },
  medium_static: { label: '中风险静态页', color: 'gold' },
  medium_js: { label: '中风险动态页', color: 'orange' },
  high_js: { label: '高风险渲染站', color: 'red' },
};

export const SOURCE_RISK_OPTIONS = Object.entries(SOURCE_RISK_META).map(([value, meta]) => ({ value, label: meta.label }));

export const SOURCE_STRATEGY_STATUS_META: Record<string, { label: string; color: string }> = {
  ready: { label: '策略完整', color: 'green' },
  candidate: { label: '候选待启用', color: 'blue' },
  needs_rules: { label: '缺规则', color: 'orange' },
  candidate_high_risk: { label: '高风险候选', color: 'red' },
};

export const SOURCE_RULE_PROFILE_LABELS: Record<string, string> = {
  authorized_api_v1: '授权结构化接口规则',
  bidding_public_list_v1: '标讯公开列表规则',
  policy_public_list_v1: '政策公开列表规则',
  market_public_list_v1: '市场公开列表规则',
  competitor_public_list_v1: '竞对公开列表规则',
  industry_public_list_v1: '行业知识网页规则',
  dynamic_public_html_probe_v1: '动态公开探测规则',
  direct_pages_v1: '直采页面规则',
  rss_feed_v1: '订阅源规则',
  public_query_api_v1: '公开查询接口规则',
};

export const SOURCE_TIER_COLOR: Record<string, string> = {
  authorized_primary: 'green',
  authority_national: 'red',
  authority_regional: 'volcano',
  industry_official: 'blue',
  subscription_source: 'cyan',
  competitor_watch: 'purple',
  candidate_high_risk: 'red',
  public_candidate: 'default',
};

export const CRAWLER_RUN_STATUS_META: Record<string, { label: string; color: string }> = {
  completed: { label: '成功', color: 'green' },
  partial: { label: '部分成功', color: 'gold' },
  error: { label: '失败', color: 'red' },
  running: { label: '运行中', color: 'blue' },
};

export const statusMeta = (status: string) => {
  if (status === 'running') return { label: '运行中', color: 'processing' };
  if (status === 'completed') return { label: '正常', color: 'green' };
  if (status === 'partial') return { label: '部分异常', color: 'orange' };
  if (status === 'error') return { label: '失败', color: 'red' };
  return { label: '待运行', color: 'default' };
};

export const formatDuration = (ms?: number | null) => {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

export const sourceTypeLabel = (type?: string) => {
  if (type === 'api') return '接口';
  if (type === 'rss') return '订阅';
  if (type === 'browser') return '渲染页';
  return '网页';
};

export const sourceTypeColor = (type?: string) => {
  if (type === 'api' || type === 'api_post') return 'red';
  if (type === 'rss') return 'blue';
  if (type === 'browser') return 'orange';
  return 'default';
};

export const sourceCapability = (status?: string) => (
  SOURCE_CAPABILITY_META[status || ''] || { label: status || '未知', color: 'default' }
);

export const sourceRuntime = (status?: string) => (
  SOURCE_RUNTIME_META[status || ''] || { label: status || '未知', color: 'default' }
);

export const sourceRisk = (record: CrawlerSourceItem) => {
  const level = record.risk_level || record.crawl_policy?.risk_level || record.selectors?.risk_level
    || inferRiskLevelBySourceType(record.selectors?.type || record.selectors?.source_type, record.category);
  return SOURCE_RISK_META[level] || { label: level || '未分级', color: 'default' };
};

export const sourceTier = (record: CrawlerSourceItem) => {
  const tier = record.source_tier;
  return {
    label: tier?.label || '未分级来源',
    color: SOURCE_TIER_COLOR[tier?.code || ''] || 'default',
    description: tier?.description || '该来源尚未完成等级识别',
  };
};

export const sourceStrategyStatus = (record: CrawlerSourceItem) => (
  SOURCE_STRATEGY_STATUS_META[record.strategy_status || ''] || {
    label: record.strategy_status_label || '待确认',
    color: 'default',
  }
);

export const sourceRuleLabel = (record: CrawlerSourceItem) => {
  const profile = record.rule_profile || record.selectors?.rule_profile;
  return profile ? SOURCE_RULE_PROFILE_LABELS[profile] || profile : '';
};

export const sourceRiskTooltip = (record: CrawlerSourceItem) => {
  const policy = record.crawl_policy || {};
  return [
    record.anti_crawl_strategy,
    record.anti_crawl_plan ? `策略：${record.anti_crawl_plan}` : '',
    policy.min_interval_seconds ? `最小间隔 ${policy.min_interval_seconds}s` : '',
    policy.max_requests_per_minute ? `每分钟最多 ${policy.max_requests_per_minute} 次` : '',
    policy.use_conditional_request ? '支持增量请求' : '',
    policy.discover_feeds ? '允许发现订阅入口' : '',
    policy.requires_browser ? '需要渲染白名单' : '',
    record.stop_rules?.length ? `停止规则：${record.stop_rules.join('、')}` : '',
  ].filter(Boolean).join('；') || '按来源级策略低频采集';
};

export const sourceStrategyTooltip = (record: CrawlerSourceItem) => [
  sourceRuleLabel(record) ? `采集规则：${sourceRuleLabel(record)}` : '',
  record.rule_note || record.selectors?.rule_note || record.selectors?.execution_note
    ? `规则说明：${record.rule_note || record.selectors?.rule_note || record.selectors?.execution_note}`
    : '',
  record.collection_strategy,
  record.strategy_gaps?.length ? `缺口：${record.strategy_gaps.join('、')}` : '',
  record.operator_action ? `下一步：${record.operator_action}` : '',
].filter(Boolean).join('；') || '暂无策略说明';

export const buildSourceSelectors = (values: Record<string, any>, existing: Record<string, any>) => {
  const selectors: Record<string, any> = { ...existing, type: values.source_type || 'official_site' };
  ['list', 'title', 'link', 'date', 'strategy', 'risk_level'].forEach((key) => {
    const value = String(values[key] || '').trim();
    if (value) selectors[key] = value;
    else delete selectors[key];
  });
  ['min_interval_seconds', 'max_requests_per_minute'].forEach((key) => {
    const rawValue = values[key];
    const value = rawValue === undefined || rawValue === null ? '' : String(rawValue).trim();
    if (value) selectors[key] = Number(value);
    else delete selectors[key];
  });
  delete selectors.source_type;
  return selectors;
};
