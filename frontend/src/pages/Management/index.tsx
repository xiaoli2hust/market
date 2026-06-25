import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  CloudServerOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchCrawlerSources,
  createCrawlerSource,
  updateCrawlerSource,
  deleteCrawlerSource,
  fetchKeywords,
  updateKeywords,
  fetchSchedule,
  updateSchedule,
  fetchCrawlerStatus,
  fetchCrawlerRuns,
  triggerCrawler,
  triggerAllCrawlers,
  fetchLLMConfig,
  updateLLMConfig,
  testLLMConnection,
  fetchLLMStats,
  fetchPrompts,
  updatePrompt,
  fetchSystemUsers,
  createSystemUser,
  updateSystemUser,
  resetUserPassword,
  deleteSystemUser,
  fetchRoles,
  fetchOperationLogs,
  fetchAPIKeys,
  createAPIKey,
  deleteAPIKey,
  toggleAPIKey,
  fetchDingtalkConfig,
  updateDingtalkConfig,
  testDingtalk,
  fetchSystemInfo,
  changeCurrentPassword,
  logout,
  getPermissionLabel,
  getApiErrorMessage,
  CrawlerSourceItem,
  CrawlerStatus,
  CrawlerRunLog,
  LLMConfigData,
  LLMStats,
  PromptTemplate,
  SystemUser,
  RoleDef,
  APIKeyItem,
} from '@/services/api';
import {
  WorkbenchPageHeader,
  WorkbenchSection,
  WorkbenchStatusRail,
} from '@/components/workbench';
import './management.less';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;
const CRAWLER_MESSAGE_KEY = 'crawler-run-status';

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  bidding: { label: '标讯雷达', color: '#f5222d' },
  policy: { label: '政策研判', color: '#13c2c2' },
  news: { label: '市场线索', color: '#1890ff' },
  competitor: { label: '竞对监控', color: '#fa8c16' },
  ai: { label: '行业知识', color: '#722ed1' },
};

const SOURCE_CATEGORY_ORDER = ['bidding', 'policy', 'news', 'competitor', 'ai'];

const TARGET_SOURCE_CATEGORY_OPTIONS = SOURCE_CATEGORY_ORDER
  .map((value) => ({ value, label: CATEGORY_LABELS[value].label }));

const Management: React.FC = () => {
  const [tab, setTab] = useState(() => {
    if (typeof window === 'undefined') return 'crawler';
    return new URLSearchParams(window.location.search).get('tab') || 'crawler';
  });

  const handleTabChange = (key: string) => {
    setTab(key);
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', `/management?tab=${key}`);
    }
  };

  return (
    <div className="mgmt">
      <WorkbenchPageHeader
        eyebrow="Command Center"
        title="管理"
        accent="中心"
        description="采集配置 · Agent 与模型 · 账号权限 · 外部集成 · 安全审计"
        extra={<Tag color="blue">所有关键操作均写入后端状态</Tag>}
      />

      <Tabs
        activeKey={tab}
        onChange={handleTabChange}
        className="mgmt-tabs edl-rise edl-rise-2"
        items={[
          { key: 'crawler', label: <span><CloudServerOutlined /> 采集配置</span>, children: <CrawlerTab /> },
          { key: 'llm', label: <span><RobotOutlined /> Agent 与模型</span>, children: <LLMTab /> },
          { key: 'users', label: <span><TeamOutlined /> 账号权限</span>, children: <UsersTab /> },
          { key: 'settings', label: <span><SettingOutlined /> 外部集成</span>, children: <SettingsTab /> },
        ]}
      />
    </div>
  );
};

/* ================================================================
   Tab 1: 爬虫管理
   ================================================================ */

// 关键词管理（与后端 crawlers/config.py 同步）
const BIDDING_KEYWORDS_CONFIG = {
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

const DIRECTION_META: Record<string, { label: string; color: string; icon: string }> = {
  toG_公安: { label: 'toG · 公安', color: '#f5222d', icon: '🚔' },
  toG_政数: { label: 'toG · 政数', color: '#1890ff', icon: '🏛️' },
  toB_零售: { label: 'toB · 零售', color: '#fa8c16', icon: '🛒' },
  toB_金融: { label: 'toB · 金融', color: '#52c41a', icon: '🏦' },
  toB_智驾: { label: 'toB · 智驾', color: '#722ed1', icon: '🚗' },
};

const DIRECTION_KEYS = Object.keys(DIRECTION_META);

const splitKeywordText = (text: string) => text.split(/[,，、]/).map(s => s.trim()).filter(Boolean);
const KEYWORD_CATEGORY_ORDER = ['policy', 'news', 'competitor', 'ai'];

const SOURCE_TYPE_OPTIONS = [
  { value: 'official_site', label: '官网/网页' },
  { value: 'rss', label: '订阅' },
  { value: 'api_post', label: '接口（候选）' },
  { value: 'browser', label: '渲染页' },
];

const SOURCE_TYPE_LABELS: Record<string, string> = {
  api: '接口',
  api_post: '接口',
  http: '网页',
  direct_pages: '直采页',
  official_site: '官网/网页',
  rss: '订阅',
  browser: '渲染页',
};

const inferRiskLevelBySourceType = (sourceType?: string, category?: string) => {
  if (sourceType === 'api') return 'authorized_api';
  if (sourceType === 'api_post') return 'public_query_api';
  if (sourceType === 'rss') return 'rss_low';
  if (sourceType === 'browser') return 'high_js';
  if (sourceType === 'direct_pages') return category === 'competitor' ? 'medium_js' : 'medium_static';
  return 'normal_public';
};

const SOURCE_CAPABILITY_META: Record<string, { label: string; color: string }> = {
  ready: { label: '已接入', color: 'green' },
  candidate: { label: '候选源', color: 'blue' },
  needs_selectors: { label: '缺解析规则', color: 'orange' },
  not_connected: { label: '未接入', color: 'red' },
};

const SOURCE_RUNTIME_META: Record<string, { label: string; color: string }> = {
  pending: { label: '未运行', color: 'default' },
  healthy: { label: '健康', color: 'green' },
  empty: { label: '空跑', color: 'gold' },
  blocked: { label: '受限', color: 'orange' },
  cooling: { label: '冷却中', color: 'purple' },
  error: { label: '异常', color: 'red' },
  skipped: { label: '已跳过', color: 'default' },
};

const SOURCE_RISK_META: Record<string, { label: string; color: string }> = {
  authorized_api: { label: '授权接口', color: 'green' },
  public_query_api: { label: '公开接口', color: 'cyan' },
  rss_low: { label: '订阅低风险', color: 'blue' },
  normal_public: { label: '普通公开页', color: 'default' },
  medium_static: { label: '中风险静态页', color: 'gold' },
  medium_js: { label: '中风险动态页', color: 'orange' },
  high_js: { label: '高风险渲染站', color: 'red' },
};

const SOURCE_RISK_OPTIONS = Object.entries(SOURCE_RISK_META).map(([value, meta]) => ({
  value,
  label: meta.label,
}));

const SOURCE_STRATEGY_STATUS_META: Record<string, { label: string; color: string }> = {
  ready: { label: '策略完整', color: 'green' },
  candidate: { label: '候选待启用', color: 'blue' },
  needs_rules: { label: '缺规则', color: 'orange' },
  candidate_high_risk: { label: '高风险候选', color: 'red' },
};

const SOURCE_RULE_PROFILE_LABELS: Record<string, string> = {
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

const SOURCE_TIER_COLOR: Record<string, string> = {
  authorized_primary: 'green',
  authority_national: 'red',
  authority_regional: 'volcano',
  industry_official: 'blue',
  subscription_source: 'cyan',
  competitor_watch: 'purple',
  candidate_high_risk: 'red',
  public_candidate: 'default',
};

const CRAWLER_RUN_STATUS_META: Record<string, { label: string; color: string }> = {
  completed: { label: '成功', color: 'green' },
  partial: { label: '部分成功', color: 'gold' },
  error: { label: '失败', color: 'red' },
  running: { label: '运行中', color: 'blue' },
};

const CrawlerTab: React.FC = () => {
  const [sources, setSources] = useState<CrawlerSourceItem[]>([]);
  const [keywords, setKeywords] = useState<{ category: string; keywords: string[] }[]>([]);
  const [schedule, setSchedule] = useState<Record<string, any> | null>(null);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus[]>([]);
  const [crawlerRuns, setCrawlerRuns] = useState<CrawlerRunLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [crawling, setCrawling] = useState<string | null>(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [editingSource, setEditingSource] = useState<CrawlerSourceItem | null>(null);
  const [sourceCategoryTab, setSourceCategoryTab] = useState('all');
  const [newSource, setNewSource] = useState({
    category: 'bidding',
    name: '',
    url: '',
    source_type: 'official_site',
    risk_level: 'normal_public',
    is_active: false,
  });
  const [keywordTab, setKeywordTab] = useState('bidding');
  const [scheduleForm] = Form.useForm();
  const [sourceForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, k, sch, cs, runs] = await Promise.all([
        fetchCrawlerSources().catch(() => []),
        fetchKeywords().catch(() => []),
        fetchSchedule().catch(() => null),
        fetchCrawlerStatus().catch(() => []),
        fetchCrawlerRuns({ limit: 12 }).catch(() => []),
      ]);
      setSources(s);
      setKeywords(k);
      setSchedule(sch);
      if (sch) {
        scheduleForm.setFieldsValue({
          crawl_frequency_per_day: sch.crawl_frequency_per_day,
          relevance_threshold: sch.relevance_threshold,
          auto_crawl_enabled: sch.auto_crawl_enabled,
        });
      }
      setCrawlerStatus(cs);
      setCrawlerRuns(runs);
    } finally {
      setLoading(false);
    }
  }, [scheduleForm]);

  useEffect(() => { load(); }, [load]);

  const handleAddSource = async () => {
    if (!newSource.name || !newSource.url) { message.warning('请填写名称和URL'); return; }
    try {
      await createCrawlerSource({
        category: newSource.category,
        name: newSource.name,
        url: newSource.url,
        selectors: {
          type: newSource.source_type,
          risk_level: newSource.risk_level || inferRiskLevelBySourceType(newSource.source_type, newSource.category),
          strategy: newSource.category === 'bidding'
            ? '候选标讯源：审核通过后再接入低频采集或接口采集'
            : '候选来源：补齐解析规则并通过连通性检查后再启用',
        },
        is_active: false,
      });
      message.success('已添加为候选源');
      setAddModalVisible(false);
      setNewSource({ category: 'bidding', name: '', url: '', source_type: 'official_site', risk_level: 'normal_public', is_active: false });
      load();
    } catch (e: any) {
      message.error(e?.data?.detail || e?.message || '添加失败');
    }
  };

  const handleToggleSource = async (source: CrawlerSourceItem, checked: boolean) => {
    try {
      await updateCrawlerSource(source.id, { is_active: checked });
      message.success(checked ? '已启用' : '已停用');
      load();
    } catch (e: any) {
      message.error(e?.data?.detail || e?.message || '当前来源尚未满足接入条件');
    }
  };

  const handleDeleteSource = async (id: number) => {
    await deleteCrawlerSource(id);
    message.success('已删除');
    load();
  };

  const openEditSource = (source: CrawlerSourceItem) => {
    const selectors = source.selectors || {};
    setEditingSource(source);
    sourceForm.setFieldsValue({
      category: source.category,
      name: source.name,
      url: source.url,
      base_url: source.base_url || '',
      source_type: selectors.type || selectors.source_type || 'official_site',
      risk_level: selectors.risk_level || source.risk_level || source.crawl_policy?.risk_level || inferRiskLevelBySourceType(selectors.type || selectors.source_type, source.category),
      min_interval_seconds: selectors.min_interval_seconds || source.crawl_policy?.min_interval_seconds || '',
      max_requests_per_minute: selectors.max_requests_per_minute || source.crawl_policy?.max_requests_per_minute || '',
      list: selectors.list || '',
      title: selectors.title || '',
      link: selectors.link || 'a@href',
      date: selectors.date || '',
      strategy: selectors.strategy || '',
    });
  };

  const handleSaveSource = async () => {
    if (!editingSource) return;
    try {
      const values = await sourceForm.validateFields();
      const selectors = buildSourceSelectors(values, editingSource.selectors || {});
      await updateCrawlerSource(editingSource.id, {
        category: values.category,
        name: values.name,
        url: values.url,
        base_url: values.base_url,
        selectors,
      });
      message.success('来源配置已保存');
      setEditingSource(null);
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.data?.detail || e?.message || '保存失败');
    }
  };

  const handleRunCrawler = async (name: string) => {
    setCrawling(name);
    message.open({
      key: CRAWLER_MESSAGE_KEY,
      type: 'loading',
      content: '正在按反爬策略低频采集，请等待结果返回',
      duration: 0,
    });
    try {
      const result = await triggerCrawler(name);
      message.success({ key: CRAWLER_MESSAGE_KEY, content: result.message || `采集完成：新增 ${result.new_saved} 条` });
      load();
    } catch (e: any) {
      message.error({ key: CRAWLER_MESSAGE_KEY, content: getApiErrorMessage(e, '采集失败') });
    }
    finally { setCrawling(null); }
  };

  const handleCrawlAll = async () => {
    setCrawling('all');
    message.open({
      key: CRAWLER_MESSAGE_KEY,
      type: 'loading',
      content: '正在逐个来源采集，公开网站会按反爬策略放慢速度，请不要重复点击',
      duration: 0,
    });
    try {
      const results = await triggerAllCrawlers();
      const totalNew = results.reduce((s: number, r: any) => s + r.new_saved, 0);
      const totalFound = results.reduce((s: number, r: any) => s + r.total_found, 0);
      message.success({ key: CRAWLER_MESSAGE_KEY, content: `全部采集完成：发现 ${totalFound} 条，新增 ${totalNew} 条` });
      load();
    } catch (e: any) {
      message.error({ key: CRAWLER_MESSAGE_KEY, content: getApiErrorMessage(e, '采集失败') });
    }
    finally { setCrawling(null); }
  };

  const handleSaveKeywords = async (category: string, text: string) => {
    const kw = text.split(/[,，\n]/).map(s => s.trim()).filter(Boolean);
    await updateKeywords(category, kw);
    message.success('关键词已保存');
    load();
  };

  const handleSaveSchedule = async () => {
    try {
      const values = await scheduleForm.validateFields();
      await updateSchedule({
        crawl_frequency_per_day: Number(values.crawl_frequency_per_day),
        relevance_threshold: Number(values.relevance_threshold),
        auto_crawl_enabled: !!values.auto_crawl_enabled,
      });
      message.success('调度配置已生效');
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.data?.detail || e?.message || '保存失败');
    }
  };

  const statusMeta = (status: string) => {
    if (status === 'running') return { label: '运行中', color: 'processing' };
    if (status === 'completed') return { label: '正常', color: 'green' };
    if (status === 'partial') return { label: '部分异常', color: 'orange' };
    if (status === 'error') return { label: '失败', color: 'red' };
    return { label: '待运行', color: 'default' };
  };

  const formatDuration = (ms?: number | null) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const sourceTypeLabel = (type?: string) => {
    if (type === 'api') return '接口';
    if (type === 'rss') return '订阅';
    if (type === 'browser') return '渲染页';
    return '网页';
  };

  const sourceTypeColor = (type?: string) => {
    if (type === 'api' || type === 'api_post') return 'red';
    if (type === 'rss') return 'blue';
    if (type === 'browser') return 'orange';
    return 'default';
  };

  const sourceCapability = (status?: string) => (
    SOURCE_CAPABILITY_META[status || ''] || { label: status || '未知', color: 'default' }
  );

  const sourceRuntime = (status?: string) => (
    SOURCE_RUNTIME_META[status || ''] || { label: status || '未知', color: 'default' }
  );

  const sourceRisk = (record: CrawlerSourceItem) => {
    const level = record.risk_level || record.crawl_policy?.risk_level || record.selectors?.risk_level
      || inferRiskLevelBySourceType(record.selectors?.type || record.selectors?.source_type, record.category);
    return SOURCE_RISK_META[level] || { label: level || '未分级', color: 'default' };
  };

  const sourceTier = (record: CrawlerSourceItem) => {
    const tier = record.source_tier;
    return {
      label: tier?.label || '未分级来源',
      color: SOURCE_TIER_COLOR[tier?.code || ''] || 'default',
      description: tier?.description || '该来源尚未完成等级识别',
    };
  };

  const sourceStrategyStatus = (record: CrawlerSourceItem) => (
    SOURCE_STRATEGY_STATUS_META[record.strategy_status || ''] || {
      label: record.strategy_status_label || '待确认',
      color: 'default',
    }
  );

  const sourceRuleLabel = (record: CrawlerSourceItem) => {
    const profile = record.rule_profile || record.selectors?.rule_profile;
    return profile ? SOURCE_RULE_PROFILE_LABELS[profile] || profile : '';
  };

  const sourceRiskTooltip = (record: CrawlerSourceItem) => {
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

  const sourceStrategyTooltip = (record: CrawlerSourceItem) => [
    sourceRuleLabel(record) ? `采集规则：${sourceRuleLabel(record)}` : '',
    record.rule_note || record.selectors?.rule_note || record.selectors?.execution_note
      ? `规则说明：${record.rule_note || record.selectors?.rule_note || record.selectors?.execution_note}`
      : '',
    record.collection_strategy,
    record.strategy_gaps?.length ? `缺口：${record.strategy_gaps.join('、')}` : '',
    record.operator_action ? `下一步：${record.operator_action}` : '',
  ].filter(Boolean).join('；') || '暂无策略说明';

  const buildSourceSelectors = (values: Record<string, any>, existing: Record<string, any>) => {
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

  const fallbackBiddingSearchKeywords = DIRECTION_KEYS.flatMap(
    (key) => ((BIDDING_KEYWORDS_CONFIG.search as any)[key] || []) as string[],
  );
  const biddingKeywordConfig = keywords.find((kw) => kw.category === 'bidding');
  const biddingSearchKeywords = biddingKeywordConfig?.keywords?.length
    ? biddingKeywordConfig.keywords
    : fallbackBiddingSearchKeywords;
  const biddingSearchKeywordCount = biddingSearchKeywords.length;
  const biddingScoringKeywordCount = DIRECTION_KEYS.reduce(
    (sum, key) => sum + splitKeywordText((BIDDING_KEYWORDS_CONFIG.scoring as any)[key] || '').length,
    0,
  );
  const otherKeywordCount = keywords
    .filter((kw) => kw.category !== 'bidding')
    .reduce((sum, kw) => sum + kw.keywords.length, 0);
  const sortedSources = [...sources].sort((a, b) => {
    const categoryDiff = SOURCE_CATEGORY_ORDER.indexOf(a.category) - SOURCE_CATEGORY_ORDER.indexOf(b.category);
    if (categoryDiff !== 0) return categoryDiff;
    const strategyDiff = (a.strategy_sort_rank ?? 999999) - (b.strategy_sort_rank ?? 999999);
    if (strategyDiff !== 0) return strategyDiff;
    return a.name.localeCompare(b.name, 'zh-CN');
  });
  const sourceCountByCategory = sortedSources.reduce<Record<string, number>>((acc, source) => {
    acc[source.category] = (acc[source.category] || 0) + 1;
    return acc;
  }, {});
  const filteredSources = sourceCategoryTab === 'all'
    ? sortedSources
    : sortedSources.filter((source) => source.category === sourceCategoryTab);
  const activeSourceCount = sortedSources.filter((source) => source.is_active).length;
  const readySourceCount = sortedSources.filter((source) => source.capability_status === 'ready').length;
  const needsRuleCount = sortedSources.filter((source) => source.strategy_status === 'needs_rules' || source.rule_status === 'missing').length;
  const blockedSourceCount = sortedSources.filter((source) => source.runtime_status === 'blocked' || source.runtime_status === 'error').length;
  const coolingSourceCount = sortedSources.filter((source) => source.runtime_status === 'cooling').length;
  const latestRun = crawlerRuns[0];
  const crawlerHealthItems = [
    {
      label: '已启用来源',
      value: `${activeSourceCount}/${sortedSources.length}`,
      meta: `${readySourceCount} 个已满足接入条件`,
      status: activeSourceCount ? 'good' as const : 'warn' as const,
    },
    {
      label: '缺规则来源',
      value: `${needsRuleCount} 个`,
      meta: needsRuleCount ? '需要补齐解析规则后再启用' : '规则完整',
      status: needsRuleCount ? 'warn' as const : 'good' as const,
    },
    {
      label: '异常或阻断',
      value: `${blockedSourceCount} 个`,
      meta: coolingSourceCount ? `${coolingSourceCount} 个冷却中` : '无冷却源',
      status: blockedSourceCount ? 'danger' as const : 'good' as const,
    },
    {
      label: '最近任务',
      value: latestRun ? CRAWLER_RUN_STATUS_META[latestRun.status]?.label || latestRun.status : '未运行',
      meta: latestRun?.started_at ? dayjs(latestRun.started_at).format('MM-DD HH:mm') : '暂无任务记录',
      status: latestRun?.status === 'error' ? 'danger' as const : latestRun ? 'good' as const : 'muted' as const,
    },
  ];

  return (
    <Spin spinning={loading}>
      <WorkbenchSection
        title="采集配置体检"
        description="先看来源是否可运行、规则是否完整、最近是否被阻断；再决定新增来源、调整关键词或执行采集。"
        action={(
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={load} size="small">刷新状态</Button>
            <Button
              type="primary"
              danger
              icon={<ThunderboltOutlined />}
              loading={crawling === 'all'}
              disabled={!!crawling}
              onClick={handleCrawlAll}
              size="small"
            >
              {crawling === 'all' ? '全量采集中...' : '一键全部采集'}
            </Button>
          </Space>
        )}
        className="mgmt-ops-health"
      >
        <WorkbenchStatusRail items={crawlerHealthItems} />
        <div className="mgmt-source-priority">
          {SOURCE_CATEGORY_ORDER.map((category) => {
            const categorySources = sortedSources.filter((source) => source.category === category);
            const categoryActive = categorySources.filter((source) => source.is_active).length;
            const categoryIssue = categorySources.filter((source) => source.strategy_status === 'needs_rules' || source.runtime_status === 'blocked' || source.runtime_status === 'error').length;
            const meta = CATEGORY_LABELS[category];
            return (
              <button
                key={category}
                type="button"
                onClick={() => setSourceCategoryTab(category)}
                className={sourceCategoryTab === category ? 'is-active' : ''}
              >
                <Tag color={meta.color}>{meta.label}</Tag>
                <strong>{categoryActive}/{categorySources.length}</strong>
                <span>{categoryIssue ? `${categoryIssue} 个待处理` : '状态正常'}</span>
              </button>
            );
          })}
        </div>
      </WorkbenchSection>

      {/* 爬虫状态卡片 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><RobotOutlined /> 采集引擎</h3>
          <Button
            type="primary"
            danger
            icon={<ThunderboltOutlined />}
            loading={crawling === 'all'}
            disabled={!!crawling}
            onClick={handleCrawlAll}
            size="small"
          >
            {crawling === 'all' ? '全量采集中...' : '一键全部采集'}
          </Button>
        </div>
        {crawling && (
          <div className="mgmt-crawler-running">
            <ThunderboltOutlined />
            <span>
              {crawling === 'all'
                ? '全量采集正在逐源执行，公开网站会按反爬策略低频访问，预计需要数分钟到十几分钟。'
                : '当前采集任务正在执行，系统会完成去重、相关性过滤和入库诊断后刷新结果。'}
            </span>
          </div>
        )}
        <Row gutter={[14, 14]}>
          {crawlerStatus.map(cs => {
            const isRunning = crawling === cs.name || crawling === 'all';
            const stats = (cs.last_run_stats || {}) as Partial<CrawlerRunLog>;
            const runExtra = (stats.extra_data || {}) as Record<string, any>;
            const health = runExtra.health_summary || {};
            const quality = runExtra.quality_summary || {};
            const sourceReports = runExtra.source_reports || [];
            const meta = statusMeta(isRunning ? 'running' : cs.status);
            const strategy = cs.strategy || {};
            const sourceDetails = cs.source_details || [];
            const sourceBreakdown = cs.source_breakdown || [];
            const effectiveCount = cs.effective_count ?? cs.total_collected;
            const filteredCount = cs.filtered_count ?? 0;
            return (
              <Col key={cs.name} xs={24} lg={12}>
                <Card size="small" className="mgmt-engine-card" style={{ borderLeft: `3px solid ${CATEGORY_LABELS[cs.category]?.color || '#999'}` }}>
                  <div className="mgmt-engine-head">
                    <div className="mgmt-engine-title">
                      <span className={`mgmt-dot ${cs.status === 'running' || isRunning ? 'is-running' : ''} ${cs.status === 'error' ? 'is-error' : ''}`} />
                      <Text strong>{cs.label}</Text>
                      <Tag color={meta.color} style={{ margin: 0, fontSize: 11 }}>{meta.label}</Tag>
                    </div>
                    <Button
                      type="link"
                      size="small"
                      loading={isRunning}
                      disabled={!!crawling}
                      onClick={() => handleRunCrawler(cs.name)}
                      style={{ padding: 0, fontSize: 12 }}
                    >
                      {isRunning ? (crawling === 'all' ? '队列中...' : '采集中...') : '采集'}
                    </Button>
                  </div>

                  <div className="mgmt-engine-counts">
                    <div>
                      <span>原始入库</span>
                      <b>{cs.total_collected}</b>
                    </div>
                    <div>
                      <span>有效信号</span>
                      <b>{effectiveCount}</b>
                    </div>
                    <div>
                      <span>过滤留档</span>
                      <b>{filteredCount}</b>
                    </div>
                    <div>
                      <span>启用来源</span>
                      <b>{cs.active_sources || sourceDetails.length || 0}</b>
                    </div>
                  </div>

                  <div className="mgmt-crawler-stats">
                    <span>发现 <b>{stats.total_found ?? '—'}</b></span>
                    <span>新增 <b>{stats.new_saved ?? '—'}</b></span>
                    <span>重复 <b>{stats.duplicates_skipped ?? '—'}</b></span>
                    <span>丢弃 <b>{stats.low_score_discarded ?? '—'}</b></span>
                    <span className={(stats.errors || 0) > 0 ? 'is-warn' : ''}>错误 <b>{stats.errors ?? '—'}</b></span>
                  </div>

                  {Object.keys(health).length > 0 && (
                    <div className="mgmt-crawler-stats">
                      <span>正常源 <b>{health.ok_sources ?? 0}</b></span>
                      <span>空源 <b>{health.empty_sources ?? 0}</b></span>
                      <span>阻断 <b>{health.blocked_sources ?? 0}</b></span>
                      {cs.category === 'bidding' && <span>金额率 <b>{Math.round((quality.amount_rate || 0) * 100)}%</b></span>}
                      <span>日期率 <b>{Math.round((quality.published_at_rate || 0) * 100)}%</b></span>
                    </div>
                  )}

                  <div className="mgmt-engine-strategy">
                    <div><span>来源类型</span><strong>{strategy.source_type || '公开数据源'}</strong></div>
                    <div><span>抓取方式</span><p>{strategy.fetch_method || '按配置来源采集'}</p></div>
                    <div><span>反爬策略</span><p>{strategy.anti_crawl || '低频请求、失败退避、来源去重'}</p></div>
                    <div><span>过滤策略</span><p>{strategy.filter_policy || '按关键词和相关性过滤'}</p></div>
                  </div>

                  <div className="mgmt-engine-sources">
                    <div className="mgmt-engine-block-title">来源配置</div>
                    {sourceDetails.length ? sourceDetails.slice(0, 3).map((source) => (
                      <div className="mgmt-engine-source" key={`${source.name}-${source.url || source.type}`}>
                        <div>
                          <Tag color={sourceTypeColor(source.type)}>{sourceTypeLabel(source.type)}</Tag>
                          {source.capability_status && (
                            <Tag color={sourceCapability(source.capability_status).color}>
                              {sourceCapability(source.capability_status).label}
                            </Tag>
                          )}
                          <strong>{source.name}</strong>
                        </div>
                        <p>{source.scope || source.strategy || '按配置策略采集'}</p>
                      </div>
                    )) : <Text type="secondary">暂无启用来源</Text>}
                    {sourceDetails.length > 3 && <Text type="secondary">另有 {sourceDetails.length - 3} 个来源</Text>}
                  </div>

                  <div className="mgmt-engine-sources">
                    <div className="mgmt-engine-block-title">入库来源分布</div>
                    {sourceBreakdown.length ? sourceBreakdown.slice(0, 4).map((source) => (
                      <div className="mgmt-engine-breakdown" key={source.name}>
                        <span>{source.name}</span>
                        <b>{source.count}</b>
                      </div>
                    )) : <Text type="secondary">暂无入库数据</Text>}
                  </div>

                  {sourceReports.length > 0 && (
                    <div className="mgmt-engine-sources">
                      <div className="mgmt-engine-block-title">本次采集诊断</div>
                      {sourceReports.slice(0, 3).map((source: any) => (
                        <Tooltip key={`${source.name}-${source.diagnosis_code}`} title={source.next_action || source.error || '暂无处理建议'}>
                          <div className="mgmt-engine-source">
                            <div>
                              <Tag color={source.severity === 'error' ? 'red' : source.severity === 'warn' ? 'orange' : 'green'}>
                                {source.diagnosis_label || source.status_label || source.status}
                              </Tag>
                              <strong>{source.name}</strong>
                            </div>
                            <p>
                              {source.anti_crawl_level || '低频合规采集'}
                              <span> · </span>
                              原始 {source.raw_count ?? source.found ?? 0} / 入库 {source.saved_count ?? 0}
                            </p>
                          </div>
                        </Tooltip>
                      ))}
                      {sourceReports.length > 3 && <Text type="secondary">另有 {sourceReports.length - 3} 个诊断项</Text>}
                    </div>
                  )}

                  <div className="mgmt-crawler-foot">
                    <span><ClockCircleOutlined /> {cs.last_run_at ? dayjs(cs.last_run_at).format('MM/DD HH:mm') : '尚未运行'}</span>
                    <span>{formatDuration(stats.duration_ms)}</span>
                  </div>
                  {cs.last_error && (
                    <Tooltip title={cs.last_error}>
                      <div className="mgmt-crawler-error">
                        <WarningOutlined /> {cs.last_error}
                      </div>
                    </Tooltip>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      </div>

      {/* 自动调度 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><ClockCircleOutlined /> 自动采集调度</h3>
          <Button type="primary" onClick={handleSaveSchedule} size="small">保存调度</Button>
        </div>
        <Form form={scheduleForm} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} md={6}>
              <Form.Item label="自动采集" name="auto_crawl_enabled" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                label="每天采集次数"
                name="crawl_frequency_per_day"
                rules={[{ required: true, message: '请填写每天采集次数' }]}
              >
                <Input type="number" min={1} max={24} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                label="标讯有效阈值"
                name="relevance_threshold"
                rules={[{ required: true, message: '请填写有效阈值' }]}
              >
                <Input type="number" min={0} max={100} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
        <Space wrap size={8}>
          <Tag color={schedule?.auto_crawl_enabled ? 'green' : 'default'}>
            {schedule?.auto_crawl_enabled ? '自动采集已启用' : '自动采集未启用'}
          </Tag>
          <Tag>运行器：{schedule?.runtime?.status || schedule?.scheduler_status || '未知'}</Tag>
          <Tag>上次运行：{schedule?.last_run_at ? dayjs(schedule.last_run_at).format('MM/DD HH:mm') : '暂无'}</Tag>
          <Tag>下次运行：{schedule?.next_run_at ? dayjs(schedule.next_run_at).format('MM/DD HH:mm') : '未安排'}</Tag>
        </Space>
        <div className="mgmt-schedule-agents">
          {Object.values(schedule?.crawler_next_runs || {}).map((item: any) => (
            <div className="mgmt-schedule-agent" key={item.name}>
              <div>
                <strong>{item.label || item.name}</strong>
                <Tag color={item.due ? 'orange' : 'default'}>{item.due ? '待运行' : '等待中'}</Tag>
                {item.last_status && (
                  <Tag color={CRAWLER_RUN_STATUS_META[item.last_status]?.color || 'default'}>
                    上次{CRAWLER_RUN_STATUS_META[item.last_status]?.label || item.last_status}
                  </Tag>
                )}
              </div>
              <p>
                上次 {item.last_run_at ? dayjs(item.last_run_at).format('MM/DD HH:mm') : '暂无'}
                <span> / </span>
                下次 {item.next_run_at ? dayjs(item.next_run_at).format('MM/DD HH:mm') : '未安排'}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 最近运行日志 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><ClockCircleOutlined /> 最近运行日志</h3>
          <Button icon={<ReloadOutlined />} onClick={load} size="small">刷新日志</Button>
        </div>
        <Table<CrawlerRunLog>
          rowKey="id"
          size="small"
          dataSource={crawlerRuns}
          pagination={false}
          columns={[
            {
              title: '引擎',
              dataIndex: 'crawler_name',
              width: 110,
              render: (name: string, record) => (
                <Space size={6}>
                  <Tag color={CATEGORY_LABELS[record.category]?.color}>{CATEGORY_LABELS[record.category]?.label || name}</Tag>
                </Space>
              ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 96,
              render: (status: string) => {
                const meta = statusMeta(status);
                return <Tag color={meta.color}>{meta.label}</Tag>;
              },
            },
            {
              title: '发现/新增',
              width: 110,
              render: (_, record) => <span className="edl-mono">{record.total_found}/{record.new_saved}</span>,
            },
            {
              title: '重复/丢弃',
              width: 110,
              render: (_, record) => <span className="edl-mono">{record.duplicates_skipped}/{record.low_score_discarded}</span>,
            },
            {
              title: '错误',
              dataIndex: 'errors',
              width: 70,
              render: (errors: number, record) => errors > 0 ? (
                <Tooltip title={record.error_message || '存在采集异常'}>
                  <Tag color="red">{errors}</Tag>
                </Tooltip>
              ) : <Tag color="green">0</Tag>,
            },
            {
              title: '耗时',
              dataIndex: 'duration_ms',
              width: 80,
              render: (ms: number | null) => <span className="edl-mono">{formatDuration(ms)}</span>,
            },
            {
              title: '运行时间',
              dataIndex: 'finished_at',
              width: 130,
              render: (value: string | null) => value ? dayjs(value).format('MM/DD HH:mm') : '—',
            },
            {
              title: '来源健康',
              dataIndex: 'extra_data',
              ellipsis: true,
              render: (extra: Record<string, any> | null) => {
                const reports = extra?.source_reports || [];
                if (!reports.length) return <Text type="secondary">—</Text>;
                const health = extra?.health_summary || {};
                const ok = health.ok_sources ?? reports.filter((item: any) => item.status === 'ok' && (item.found || 0) > 0).length;
                const empty = health.empty_sources ?? reports.filter((item: any) => item.status === 'ok' && !(item.found || 0)).length;
                const failed = health.error_sources ?? reports.filter((item: any) => item.status === 'error').length;
                const blocked = health.blocked_sources ?? reports.filter((item: any) => ['robots_blocked', 'challenge_detected', 'forbidden', 'rate_limited'].includes(item.diagnosis_code)).length;
                const usedKeywords = reports.flatMap((item: any) => item.query_keywords || []);
                const diagnosisText = reports
                  .slice(0, 8)
                  .map((item: any) => `${item.name}：${item.diagnosis_label || item.status_label || item.status}${item.next_action ? `，${item.next_action}` : ''}`)
                  .join('；');
                const label = `${ok} 正常${empty ? ` · ${empty} 空` : ''}${blocked ? ` · ${blocked} 阻断` : ''}${failed ? ` · ${failed} 异常` : ''}${usedKeywords.length ? ` · 查询词 ${usedKeywords.length}` : ''}`;
                return (
                  <Tooltip title={diagnosisText || '本次未使用查询词'}>
                    <span>{label}</span>
                  </Tooltip>
                );
              },
            },
          ]}
          locale={{ emptyText: <Empty description="暂无运行日志" /> }}
        />
      </div>

      {/* 关键词管理 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><FileSearchOutlined /> 关键词管理</h3>
          <Text type="secondary" style={{ fontSize: 12 }}>
            标讯搜索词 {biddingSearchKeywordCount} 个 · 标讯评分词 {biddingScoringKeywordCount} 个 · 政策/市场/竞对/行业知识 {otherKeywordCount} 个
          </Text>
        </div>

        <Tabs
          activeKey={keywordTab}
          onChange={setKeywordTab}
          size="small"
          items={[
            {
              key: 'bidding',
              label: <span><FileSearchOutlined /> 标讯</span>,
              children: (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      标讯召回词可直接编辑，分方向卡片用于核对业务口径；评分关键词用于采集后的匹配打分。
                    </Text>
                  </div>

                  <Card size="small" title="标讯召回关键词（可编辑）" style={{ marginBottom: 20 }}>
                    <TextArea
                      key={`bidding-keywords-${biddingSearchKeywords.join('|')}`}
                      defaultValue={biddingSearchKeywords.join(', ')}
                      rows={4}
                      placeholder="关键词用逗号或换行分隔"
                      onBlur={(e) => handleSaveKeywords('bidding', e.target.value)}
                    />
                  </Card>

                  {/* 搜索关键词 */}
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      分方向召回词参考
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.search).map(([dir, kws]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        return (
                          <Col key={dir} xs={24} md={12} lg={8}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{(kws as string[]).length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {(kws as string[]).map((kw: string, i: number) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>

                  {/* 评分关键词 */}
                  <div>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      评分关键词（采集后匹配打分使用）
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.scoring).map(([dir, kwStr]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        const kwList = splitKeywordText(kwStr as string);
                        return (
                          <Col key={dir} xs={24} md={12}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{kwList.length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {kwList.slice(0, 20).map((kw, i) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                                {kwList.length > 20 && (
                                  <Tag style={{ margin: '1px 2px', fontSize: 11, color: '#999' }}>+{kwList.length - 20} 个</Tag>
                                )}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>
                </div>
              ),
            },
            ...KEYWORD_CATEGORY_ORDER.map((category) => {
              const kw = keywords.find((item) => item.category === category) || { category, keywords: [] };
              const meta = CATEGORY_LABELS[category] || { label: category, color: 'default' };
              return {
                key: category,
                label: <span><GlobalOutlined /> {meta.label}关键词</span>,
                children: (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
                      {meta.label}采集使用的关键词。关键词用逗号或换行分隔，修改后离开输入框自动保存。
                    </Text>
                    <Card size="small" title={<Tag color={meta.color}>{meta.label}</Tag>}>
                      <TextArea
                        key={`keywords-${category}-${kw.keywords.join('|')}`}
                        defaultValue={kw.keywords.join(', ')}
                        rows={6}
                        placeholder="关键词用逗号或换行分隔"
                        onBlur={(e) => handleSaveKeywords(category, e.target.value)}
                      />
                    </Card>
                  </div>
                ),
              };
            }),
          ]}
        />
      </div>

      {/* 目标站点管理 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><DatabaseOutlined /> 目标站点管理</h3>
          <Button icon={<PlusOutlined />} onClick={() => setAddModalVisible(true)} size="small">添加站点</Button>
        </div>
        <Paragraph type="secondary" style={{ marginTop: -4, fontSize: 12 }}>
          各类采集源统一在这里管理。列表按来源等级、反爬风险、策略完整度排序；候选源补齐规则并通过检查后再启用，避免无关网站污染业务视图。
        </Paragraph>
        <Tabs
          activeKey={sourceCategoryTab}
          onChange={setSourceCategoryTab}
          size="small"
          items={[
            { key: 'all', label: `全部 ${sortedSources.length}` },
            ...SOURCE_CATEGORY_ORDER.map((category) => ({
              key: category,
              label: `${CATEGORY_LABELS[category].label} ${sourceCountByCategory[category] || 0}`,
            })),
          ]}
        />
        <Table
          rowKey="id"
          size="small"
          dataSource={filteredSources}
          scroll={{ x: 1500 }}
          pagination={{
            pageSize: 12,
            showSizeChanger: true,
            pageSizeOptions: [12, 24, 48],
            showTotal: (total) => `共 ${total} 个来源`,
          }}
          columns={[
            { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color={CATEGORY_LABELS[c]?.color}>{CATEGORY_LABELS[c]?.label || c}</Tag> },
            {
              title: '来源等级',
              dataIndex: 'source_tier',
              width: 146,
              render: (_: any, record: CrawlerSourceItem) => {
                const tier = sourceTier(record);
                return (
                  <Tooltip title={tier.description}>
                    <Tag color={tier.color}>{tier.label}</Tag>
                  </Tooltip>
                );
              },
            },
            { title: '名称', dataIndex: 'name', width: 160, render: (t: string) => <Text strong>{t}</Text> },
            {
              title: '来源类型',
              dataIndex: 'selectors',
              width: 96,
              render: (selectors: Record<string, any> | null) => {
                const type = selectors?.type || 'official_site';
                return <Tag>{SOURCE_TYPE_LABELS[type] || type}</Tag>;
              },
            },
            {
              title: '反爬级别',
              dataIndex: 'risk_level',
              width: 128,
              render: (_: string, record: CrawlerSourceItem) => {
                const meta = sourceRisk(record);
                return (
                  <Tooltip title={sourceRiskTooltip(record)}>
                    <Tag color={meta.color}>{meta.label}</Tag>
                  </Tooltip>
                );
              },
            },
            {
              title: '策略状态',
              dataIndex: 'strategy_status',
              width: 116,
              render: (_: string, record: CrawlerSourceItem) => {
                const meta = sourceStrategyStatus(record);
                return (
                  <Tooltip title={sourceStrategyTooltip(record)}>
                    <Tag color={meta.color}>{meta.label}</Tag>
                  </Tooltip>
                );
              },
            },
            {
              title: '接入状态',
              dataIndex: 'capability_status',
              width: 118,
              render: (status: string, record: CrawlerSourceItem) => {
                const meta = sourceCapability(status);
                return (
                  <Tooltip title={record.capability_reason || '暂无说明'}>
                    <Tag color={meta.color}>{meta.label}</Tag>
                  </Tooltip>
                );
              },
            },
            {
              title: '运行状态',
              dataIndex: 'runtime_status',
              width: 150,
              render: (status: string, record: CrawlerSourceItem) => {
                const meta = sourceRuntime(status);
                const checkedAt = record.last_checked_at ? dayjs(record.last_checked_at).format('MM/DD HH:mm') : '尚未运行';
                const cooldown = record.cooldown_until ? `冷却到 ${dayjs(record.cooldown_until).format('MM/DD HH:mm')}` : '';
                const cursorTitle = record.last_cursor?.title ? `最近入库：${record.last_cursor.title}` : '';
                const tip = [
                  record.runtime_reason || record.last_diagnosis_label || '暂无运行记录',
                  `最近处理：发现 ${record.last_found || 0}，入库 ${record.last_saved || 0}`,
                  `最近检查：${checkedAt}`,
                  cursorTitle,
                  record.consecutive_failures ? `连续异常：${record.consecutive_failures}` : '',
                  cooldown,
                ].filter(Boolean).join('；');
                return (
                  <Tooltip title={tip}>
                    <Space size={4} direction="vertical">
                      <Tag color={meta.color}>{meta.label}</Tag>
                      <Text type="secondary" style={{ fontSize: 11 }}>{checkedAt}</Text>
                    </Space>
                  </Tooltip>
                );
              },
            },
            { title: 'URL', dataIndex: 'url', ellipsis: true, render: (u: string) => <Text copyable style={{ fontSize: 12 }}>{u}</Text> },
            {
              title: '策略',
              dataIndex: 'selectors',
              ellipsis: true,
              render: (selectors: Record<string, any> | null, record: CrawlerSourceItem) => {
                const strategy = record.collection_strategy || selectors?.strategy || '按配置来源低频采集，入库后做相关性过滤';
                const plan = record.anti_crawl_plan || record.anti_crawl_strategy || '';
                const rule = sourceRuleLabel(record);
                return (
                  <Tooltip title={sourceStrategyTooltip(record)}>
                    <Space direction="vertical" size={0} style={{ maxWidth: 320 }}>
                      <Text type="secondary" ellipsis style={{ fontSize: 12 }}>{strategy}</Text>
                      {rule && <Text type="secondary" ellipsis style={{ fontSize: 11 }}>{rule}</Text>}
                      {plan && <Text type="secondary" ellipsis style={{ fontSize: 11 }}>{plan}</Text>}
                    </Space>
                  </Tooltip>
                );
              },
            },
            {
              title: '启用',
              dataIndex: 'is_active',
              width: 86,
              render: (v: boolean, record: CrawlerSourceItem) => (
                <Tooltip title={!v && record.capability_status !== 'ready' ? record.capability_reason : undefined}>
                  <Switch
                    size="small"
                    checked={v}
                    disabled={!!record.selectors?.protected || (!v && record.capability_status !== 'ready')}
                    aria-label={`${v ? '停用' : '启用'}采集源：${record.name}`}
                    onChange={(checked) => handleToggleSource(record, checked)}
                  />
                </Tooltip>
              ),
            },
            { title: '操作', key: 'action', width: 92, render: (_: any, r: CrawlerSourceItem) => (
              <Space size={2}>
                <Tooltip title={r.selectors?.protected ? '当前主链路来源，不允许编辑' : '编辑解析规则'}>
                  <Button
                    type="text"
                    disabled={!!r.selectors?.protected}
                    size="small"
                    aria-label={`编辑采集源：${r.name}`}
                    title="编辑解析规则"
                    icon={<EditOutlined />}
                    onClick={() => openEditSource(r)}
                  />
                </Tooltip>
                {r.selectors?.protected ? (
                  <Tooltip title="当前主链路来源，不允许删除">
                    <Button
                      type="text"
                      disabled
                      size="small"
                      aria-label={`删除采集源：${r.name}`}
                      title="当前主链路来源，不允许删除"
                      icon={<DeleteOutlined />}
                    />
                  </Tooltip>
                ) : (
                  <Popconfirm title="确定删除？" onConfirm={() => handleDeleteSource(r.id)}>
                    <Button
                      type="text"
                      danger
                      size="small"
                      aria-label={`删除采集源：${r.name}`}
                      title="删除采集源"
                      icon={<DeleteOutlined />}
                    />
                  </Popconfirm>
                )}
              </Space>
            )},
          ]}
        />
      </div>

      {/* 添加站点 Modal */}
      <Modal title="添加目标站点" open={addModalVisible} onOk={handleAddSource} onCancel={() => setAddModalVisible(false)} okText="添加">
        <Form layout="vertical">
          <Form.Item label="分类">
            <Select value={newSource.category} onChange={v => setNewSource(s => ({
              ...s,
              category: v,
              risk_level: inferRiskLevelBySourceType(s.source_type, v),
            }))}
              options={TARGET_SOURCE_CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item label="采集方式">
            <Select
              value={newSource.source_type}
              onChange={v => setNewSource(s => ({
                ...s,
                source_type: v,
                risk_level: inferRiskLevelBySourceType(v, s.category),
              }))}
              options={SOURCE_TYPE_OPTIONS}
            />
          </Form.Item>
          <Form.Item label="反爬级别">
            <Select
              value={newSource.risk_level}
              onChange={v => setNewSource(s => ({ ...s, risk_level: v }))}
              options={SOURCE_RISK_OPTIONS}
            />
          </Form.Item>
          <Form.Item label="名称" required>
            <Input value={newSource.name} onChange={e => setNewSource(s => ({ ...s, name: e.target.value }))} placeholder="如：自然资源部" />
          </Form.Item>
          <Form.Item label="URL" required>
            <Input value={newSource.url} onChange={e => setNewSource(s => ({ ...s, url: e.target.value }))} placeholder="https://..." />
          </Form.Item>
          <Form.Item label="是否立即启用">
            <Switch checked={false} disabled />
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>新增站点先作为候选源，补齐解析规则后再启用。</Text>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑站点 Modal */}
      <Modal
        title={`编辑来源：${editingSource?.name || ''}`}
        open={!!editingSource}
        onOk={handleSaveSource}
        onCancel={() => setEditingSource(null)}
        width={760}
        okText="保存配置"
      >
        <Form form={sourceForm} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
                <Select
                  options={TARGET_SOURCE_CATEGORY_OPTIONS}
                  onChange={(value) => sourceForm.setFieldsValue({
                    risk_level: inferRiskLevelBySourceType(sourceForm.getFieldValue('source_type'), value),
                  })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="采集方式" name="source_type" rules={[{ required: true, message: '请选择采集方式' }]}>
                <Select
                  options={SOURCE_TYPE_OPTIONS}
                  onChange={(value) => sourceForm.setFieldsValue({
                    risk_level: inferRiskLevelBySourceType(value, sourceForm.getFieldValue('category')),
                  })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="反爬级别" name="risk_level" rules={[{ required: true, message: '请选择反爬级别' }]}>
                <Select options={SOURCE_RISK_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item label="最小间隔（秒）" name="min_interval_seconds">
                <Input placeholder="自动" />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item label="每分钟上限" name="max_requests_per_minute">
                <Input placeholder="自动" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="名称" name="name" rules={[{ required: true, message: '请填写名称' }]}>
                <Input placeholder="来源名称" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="URL" name="url" rules={[{ required: true, message: '请填写 URL' }]}>
                <Input placeholder="https://..." />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item label="Base URL" name="base_url">
                <Input placeholder="相对链接补全用；为空时使用 URL" />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', border: '1px dashed var(--border)', borderRadius: 6 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              网页来源需要列表和标题解析规则；订阅来源只需 URL；接口和渲染页会先作为候选源保留。
            </Text>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="列表解析规则" name="list">
                <Input placeholder="例如：.list li, tr" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="标题解析规则" name="title">
                <Input placeholder="例如：a, .title a" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="链接解析规则" name="link">
                <Input placeholder="例如：a@href" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="日期解析规则" name="date">
                <Input placeholder="例如：.date, .time" />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item label="采集策略" name="strategy">
                <TextArea rows={3} placeholder="低频采集、遵守 robots、失败退避、仅保留高相关内容" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 2: 大模型工作台
   ================================================================ */

const LLMTab: React.FC = () => {
  const [config, setConfig] = useState<LLMConfigData | null>(null);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [stats, setStats] = useState<LLMStats | null>(null);
  const [testing, setTesting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [configForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, p, s] = await Promise.all([
        fetchLLMConfig().catch(() => null),
        fetchPrompts().catch(() => []),
        fetchLLMStats().catch(() => null),
      ]);
      setConfig(c);
      setPrompts(p);
      setStats(s);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const r = await testLLMConnection();
      if (r.success) message.success(r.message);
      else message.error(r.message);
    } catch (e: any) { message.error(getApiErrorMessage(e, '测试失败')); }
    finally { setTesting(false); }
  };

  const formatLatency = (ms?: number) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      await updateLLMConfig(values);
      message.success('配置已保存');
      setEditing(false);
      load();
    } catch { /* validation */ }
  };

  const handleSavePrompt = async () => {
    if (!editingPrompt) return;
    await updatePrompt(editingPrompt.scene, { template: editText });
    message.success('Prompt 已保存');
    setEditingPrompt(null);
    load();
  };

  return (
    <Spin spinning={loading}>
      {/* 模型配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><RobotOutlined /> 模型配置</h3>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleTest} loading={testing} size="small">测试连接</Button>
            {!editing && <Button icon={<EditOutlined />} onClick={() => { setEditing(true); configForm.setFieldsValue({ model_name: config?.model_name, api_base_url: config?.api_base_url, api_key: '', default_temperature: config?.default_temperature }); }} size="small">编辑</Button>}
          </Space>
        </div>

        {config && !editing && (
          <Descriptions size="small" bordered column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="当前模型"><Tag color="blue">{config.model_name}</Tag></Descriptions.Item>
            <Descriptions.Item label="API Base URL"><Text style={{ fontSize: 12 }}>{config.api_base_url}</Text></Descriptions.Item>
            <Descriptions.Item label="API Key">
              <Tag color={config.configured ? 'green' : 'orange'}>{config.configured ? '已配置' : '未配置'}</Tag>
              <Text style={{ fontSize: 12, marginLeft: 8 }}>{config.api_key_masked}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Temperature">{config.default_temperature}</Descriptions.Item>
          </Descriptions>
        )}

        {editing && (
          <Card size="small">
            <Form form={configForm} layout="vertical">
              <Row gutter={16}>
                <Col xs={24} md={8}>
                  <Form.Item label="模型名称" name="model_name" rules={[{ required: true }]}>
                    <Select options={[
                      { value: 'deepseek-chat', label: 'DeepSeek Chat' },
                      { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
                      { value: 'qwen-turbo', label: 'Qwen Turbo (通义千问)' },
                      { value: 'qwen-plus', label: 'Qwen Plus (通义千问)' },
                      { value: 'gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={10}>
                  <Form.Item label="API Base URL" name="api_base_url" rules={[{ required: true }]}>
                    <Input placeholder="https://api.deepseek.com" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item label="Temperature" name="default_temperature">
                    <Input type="number" min={0} max={1} step={0.1} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="API Key（留空表示不修改）" name="api_key">
                <Input.Password placeholder="留空则保留已配置 Key" />
              </Form.Item>
              <Space>
                <Button type="primary" onClick={handleSaveConfig}>保存配置</Button>
                <Button onClick={() => setEditing(false)}>取消</Button>
              </Space>
            </Form>
          </Card>
        )}

        {!config && <Empty description="LLM 配置未初始化" />}
      </div>

      {/* 调用审计 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><DatabaseOutlined /> 调用审计</h3>
          <Button icon={<ReloadOutlined />} onClick={load} size="small">刷新</Button>
        </div>
        {stats?.implemented ? (
          <>
            <div className="mgmt-llm-stats">
              <div><span>今日调用</span><b>{stats.today_calls}</b></div>
              <div><span>今日 Token</span><b>{stats.todayTokens}</b></div>
              <div><span>今日失败</span><b>{stats.todayErrors || 0}</b></div>
              <div><span>平均耗时</span><b>{formatLatency(stats.todayAvgLatencyMs)}</b></div>
              <div><span>本周调用</span><b>{stats.weekCalls}</b></div>
              <div><span>本周 Token</span><b>{stats.weekTokens}</b></div>
            </div>
            <div className="mgmt-llm-scenes">
              {Object.entries(stats.byScene || {}).length ? Object.entries(stats.byScene).map(([scene, item]) => (
                <Tag key={scene}>
                  {scene} · {item.calls} 次 · {item.tokens} token{item.errors ? ` · 失败 ${item.errors}` : ''}
                </Tag>
              )) : <Text type="secondary">暂无调用记录</Text>}
            </div>
            {!!stats.recentErrors?.length && (
              <div className="mgmt-llm-errors">
                {stats.recentErrors.map((err, index) => (
                  <Tooltip title={err.error_message || '调用失败'} key={`${err.scene}-${index}`}>
                    <Tag color="red">{err.scene} · {err.created_at ? dayjs(err.created_at).format('MM/DD HH:mm') : '未知时间'}</Tag>
                  </Tooltip>
                ))}
              </div>
            )}
          </>
        ) : (
          <Empty description={stats?.message || '暂无调用审计'} />
        )}
      </div>

      {/* Prompt 模板 */}
      <div className="mgmt-section">
        <h3>Prompt 模板管理</h3>
        <Row gutter={[12, 12]}>
          {prompts.map(p => (
            <Col key={p.scene} xs={24} md={12}>
              <Card size="small" title={<><Text strong>{p.name}</Text> <Tag style={{ marginLeft: 8 }}>{p.scene}</Tag></>}
                extra={<Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingPrompt(p); setEditText(p.template); }}>编辑</Button>}>
                <Paragraph ellipsis={{ rows: 3 }} style={{ fontSize: 12, color: 'var(--ink-faint)', margin: 0 }}>
                  {p.template}
                </Paragraph>
                <div style={{ marginTop: 8 }}>
                  <Tag>温度 {p.temperature}</Tag>
                  <Tag>Max {p.max_tokens} tokens</Tag>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 编辑 Prompt Modal */}
      <Modal title={`编辑 Prompt：${editingPrompt?.name || ''}`} open={!!editingPrompt} onOk={handleSavePrompt} onCancel={() => setEditingPrompt(null)} width={700} okText="保存">
        <TextArea value={editText} onChange={e => setEditText(e.target.value)} rows={10} style={{ fontFamily: 'var(--mono)', fontSize: 13 }} />
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 3: 账号与权限
   ================================================================ */

const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [total, setTotal] = useState(0);
  const [roles, setRoles] = useState<RoleDef[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [addVisible, setAddVisible] = useState(false);
  const [resetVisible, setResetVisible] = useState(false);
  const [selfPwdVisible, setSelfPwdVisible] = useState(false);
  const [resetUserId, setResetUserId] = useState<number>(0);
  const [form] = Form.useForm();
  const [resetForm] = Form.useForm();
  const [selfPwdForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r, l] = await Promise.all([
        fetchSystemUsers().catch(() => ({ total: 0, items: [] })),
        fetchRoles().catch(() => []),
        fetchOperationLogs().catch(() => ({ total: 0, items: [] })),
      ]);
      setUsers(u.items);
      setTotal(u.total);
      setRoles(r);
      setLogs(l.items);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createSystemUser(values);
      message.success('用户已创建');
      setAddVisible(false);
      form.resetFields();
      load();
    } catch { /* validation error */ }
  };

  const handleReset = async () => {
    try {
      const { password } = await resetForm.validateFields();
      await resetUserPassword(resetUserId, password);
      message.success('密码已重置');
      setResetVisible(false);
      resetForm.resetFields();
    } catch { /* validation error */ }
  };

  const handleChangeOwnPassword = async () => {
    try {
      const values = await selfPwdForm.validateFields();
      if (values.new_password !== values.confirm_password) {
        message.error('两次输入的新密码不一致');
        return;
      }
      await changeCurrentPassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      message.success('密码已修改，请重新登录');
      setSelfPwdVisible(false);
      selfPwdForm.resetFields();
      await logout();
      window.location.href = '/user/login';
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.data?.detail || e?.message || '密码修改失败');
    }
  };

  const handleDelete = async (id: number) => {
    await deleteSystemUser(id);
    message.success('已删除');
    load();
  };

  const handleToggleActive = async (user: SystemUser) => {
    await updateSystemUser(user.id, { is_active: !user.is_active });
    message.success(user.is_active ? '已禁用' : '已启用');
    load();
  };

  return (
    <Spin spinning={loading}>
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><SafetyOutlined /> 当前账号安全</h3>
          <Button size="small" onClick={() => setSelfPwdVisible(true)}>
            修改我的密码
          </Button>
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>
          密码修改后需要重新登录，防止旧登录态继续使用。
        </Text>
      </div>

      {/* 用户列表 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><TeamOutlined /> 用户列表 <Tag>{total}</Tag></h3>
          <Button icon={<PlusOutlined />} onClick={() => setAddVisible(true)} size="small" type="primary" danger>新增用户</Button>
        </div>
        <Table rowKey="id" size="small" dataSource={users} pagination={false}
          columns={[
            { title: '用户名', dataIndex: 'username', width: 120, render: (t: string, r: SystemUser) => <><Text strong>{t}</Text><br /><Text type="secondary" style={{ fontSize: 11 }}>{r.display_name}</Text></> },
            { title: '角色', dataIndex: 'role_label', width: 110, render: (l: string, r: SystemUser) => <Tag color={r.role === 'super_admin' ? 'red' : r.role === 'admin' ? 'blue' : 'default'}>{l}</Tag> },
            { title: '状态', dataIndex: 'is_active', width: 80, render: (v: boolean) => v ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag> },
            { title: '创建时间', dataIndex: 'created_at', width: 120, render: (t: string) => <span className="edl-mono" style={{ fontSize: 11 }}>{t ? dayjs(t).format('YYYY·MM·DD') : '—'}</span> },
            { title: '操作', key: 'action', width: 180, render: (_: any, r: SystemUser) => (
              <Space size={4}>
                <Button type="link" size="small" onClick={() => { setResetUserId(r.id); setResetVisible(true); }}>重置密码</Button>
                <Button type="link" size="small" onClick={() => handleToggleActive(r)}>{r.is_active ? '禁用' : '启用'}</Button>
                {r.username !== 'admin' && <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}><Button type="link" size="small" danger>删除</Button></Popconfirm>}
              </Space>
            )},
          ]}
        />
      </div>

      {/* 角色定义 */}
      <div className="mgmt-section">
        <h3><SafetyOutlined /> 角色权限矩阵</h3>
        <Row gutter={[12, 12]}>
          {roles.map(r => (
            <Col key={r.key} xs={24} md={8}>
              <Card size="small" title={<Tag color={r.key === 'super_admin' ? 'red' : r.key === 'admin' ? 'blue' : 'default'}>{r.label}</Tag>}>
                <div style={{ fontSize: 12, color: 'var(--ink-faint)' }}>
                  {r.permissions.includes('*') ? (
                    <Text type="success">全部权限</Text>
                  ) : (
                    <Space wrap size={4}>{r.permissions.map(p => <Tag key={p} style={{ fontSize: 10 }}>{getPermissionLabel(p)}</Tag>)}</Space>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 操作日志 */}
      <div className="mgmt-section">
        <h3>操作日志</h3>
        {logs.length === 0 ? <Empty description="暂无日志" /> : (
          <Table rowKey="id" size="small" dataSource={logs} pagination={{ pageSize: 10 }}
            columns={[
              { title: '操作人', dataIndex: 'username', width: 100 },
              { title: '操作', dataIndex: 'action', width: 120 },
              { title: '目标', dataIndex: 'target', ellipsis: true },
              { title: '时间', dataIndex: 'created_at', width: 140, render: (t: string) => <span className="edl-mono" style={{ fontSize: 11 }}>{t ? dayjs(t).format('MM·DD HH:mm') : '—'}</span> },
            ]}
          />
        )}
      </div>

      {/* 新增用户 Modal */}
      <Modal title="新增用户" open={addVisible} onOk={handleCreate} onCancel={() => setAddVisible(false)} okText="创建">
        <Form form={form} layout="vertical">
          <Form.Item label="用户名" name="username" rules={[{ required: true }]}><Input placeholder="英文用户名" /></Form.Item>
          <Form.Item label="显示名称" name="display_name"><Input placeholder="中文名" /></Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, min: 8, message: '至少8位' }]}><Input.Password /></Form.Item>
          <Form.Item label="角色" name="role" initialValue="viewer" rules={[{ required: true }]}>
            <Select options={roles.map(r => ({ value: r.key, label: r.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重置密码 Modal */}
      <Modal title="重置密码" open={resetVisible} onOk={handleReset} onCancel={() => setResetVisible(false)} okText="确认重置">
        <Form form={resetForm} layout="vertical">
          <Form.Item label="新密码" name="password" rules={[{ required: true, min: 8, message: '至少8位' }]}><Input.Password placeholder="输入新密码" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="修改我的密码"
        open={selfPwdVisible}
        onOk={handleChangeOwnPassword}
        onCancel={() => setSelfPwdVisible(false)}
        okText="确认修改"
      >
        <Form form={selfPwdForm} layout="vertical">
          <Form.Item label="当前密码" name="current_password" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item label="新密码" name="new_password" rules={[{ required: true, min: 8, message: '至少8位' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item label="确认新密码" name="confirm_password" rules={[{ required: true, message: '请再次输入新密码' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 4: 接口与密钥
   ================================================================ */

const SettingsTab: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<APIKeyItem[]>([]);
  const [dingtalk, setDingtalk] = useState<any>(null);
  const [sysInfo, setSysInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [testingDing, setTestingDing] = useState(false);
  const [dingForm] = Form.useForm();
  const [jianyuForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [k, d, s] = await Promise.all([
        fetchAPIKeys().catch(() => []),
        fetchDingtalkConfig().catch(() => null),
        fetchSystemInfo().catch(() => null),
      ]);
      setApiKeys(k);
      setDingtalk(d);
      setSysInfo(s);
      if (d) {
        dingForm.setFieldsValue({
          delivery_mode: d.delivery_mode || 'webhook',
          webhook_url: d.webhook_url !== '未配置' ? d.webhook_url : '',
          secret: '',
          app_key: d.app_key || '',
          app_secret: '',
          app_id: d.app_id || '',
          agent_id: d.agent_id || '',
          robot_code: d.robot_code || '',
          open_conversation_id: d.open_conversation_id || '',
          cool_app_code: d.cool_app_code || '',
        });
        jianyuForm.setFieldsValue({
          jianyu_username: d.jianyu_username || '',
          jianyu_password: '',
          jianyu_api_key: '',
        });
      }
    } finally { setLoading(false); }
  }, [dingForm, jianyuForm]);

  useEffect(() => { load(); }, [load]);

  const handleCreateKey = async () => {
    const name = `Key-${dayjs().format('MMDD-HHmm')}`;
    const result = await createAPIKey({ name, purpose: 'general' });
    Modal.success({
      title: 'API Key 已生成',
      content: (
        <div>
          <Paragraph type="secondary" style={{ marginBottom: 8 }}>
            完整 Key 只在本次创建后展示一次，请现在复制。
          </Paragraph>
          <Text copyable={{ text: result.key_value }} style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
            {result.key_value}
          </Text>
        </div>
      ),
    });
    load();
  };

  const handleDeleteKey = async (id: number) => {
    await deleteAPIKey(id);
    message.success('已删除');
    load();
  };

  const handleToggleKey = async (id: number) => {
    await toggleAPIKey(id);
    message.success('Key 状态已更新');
    load();
  };

  const handleSaveDing = async () => {
    const values = await dingForm.validateFields();
    await updateDingtalkConfig({
      delivery_mode: values.delivery_mode,
      webhook_url: values.webhook_url,
      secret: values.secret,
      app_key: values.app_key,
      app_secret: values.app_secret,
      app_id: values.app_id,
      agent_id: values.agent_id,
      robot_code: values.robot_code,
      open_conversation_id: values.open_conversation_id,
      cool_app_code: values.cool_app_code,
    });
    message.success('钉钉配置已保存');
    load();
  };

  const handleSaveJianyu = async () => {
    const values = await jianyuForm.validateFields();
    await updateDingtalkConfig({
      jianyu_username: values.jianyu_username,
      jianyu_password: values.jianyu_password,
      jianyu_api_key: values.jianyu_api_key,
    });
    message.success('结构化标讯配置已保存');
    load();
  };

  const handleTestDing = async () => {
    setTestingDing(true);
    try {
      const r = await testDingtalk();
      if (r.success) message.success(r.message);
      else {
        Modal.error({
          title: '钉钉测试发送失败',
          content: (
            <div>
              <Paragraph style={{ marginBottom: 8 }}>{r.message}</Paragraph>
              {r.raw?.errcode !== undefined && (
                <Text type="secondary">错误码：{r.raw.errcode}</Text>
              )}
            </div>
          ),
        });
      }
    } catch (e: any) { message.error(getApiErrorMessage(e, '测试失败')); }
    finally { setTestingDing(false); }
  };

  return (
    <Spin spinning={loading}>
      {/* API Keys */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><KeyOutlined /> API Key 管理</h3>
          <Button icon={<PlusOutlined />} onClick={handleCreateKey} size="small" type="primary" danger>生成新 Key</Button>
        </div>
        {apiKeys.length === 0 ? <Empty description="暂无 API Key" /> : (
          <Table rowKey="id" size="small" dataSource={apiKeys} pagination={false}
            columns={[
              { title: '名称', dataIndex: 'name', width: 160 },
              { title: '用途', dataIndex: 'purpose', width: 100, render: (p: string) => <Tag>{p}</Tag> },
              { title: 'Key（脱敏）', dataIndex: 'key_masked', render: (k: string) => <Text style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{k}</Text> },
              { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) => v ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag> },
              { title: '操作', key: 'action', width: 120, render: (_: any, r: APIKeyItem) => (
                <Space size={4}>
                  <Button type="link" size="small" onClick={() => handleToggleKey(r.id)}>
                    {r.is_active ? '禁用' : '启用'}
                  </Button>
                  <Popconfirm title="确定删除？" onConfirm={() => handleDeleteKey(r.id)}>
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              )},
            ]}
          />
        )}
      </div>

      {/* 钉钉配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><SendOutlined /> 钉钉推送配置</h3>
          <Space>
            <Button onClick={handleTestDing} loading={testingDing} size="small">测试发送</Button>
            <Button type="primary" onClick={handleSaveDing} size="small">保存配置</Button>
          </Space>
        </div>
        <Form form={dingForm} layout="vertical">
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 8 }}>基础配置 · 钉钉机器人用于接收销售日报、推送报告和速递通知</div>
            <Space size={[6, 6]} wrap>
              <Tag color="blue">自定义机器人</Tag>
              <Tag color={dingtalk?.delivery_mode === 'openapi' ? 'purple' : 'cyan'}>{dingtalk?.delivery_mode === 'openapi' ? 'OpenAPI 发送' : 'Webhook 发送'}</Tag>
              <Tag color={dingtalk?.configured ? 'green' : 'default'}>{dingtalk?.configured ? 'Webhook 已配置' : 'Webhook 未配置'}</Tag>
              <Tag color={dingtalk?.sign_configured ? 'green' : 'orange'}>{dingtalk?.sign_configured ? '加签已配置' : '加签未配置'}</Tag>
              <Tag color={dingtalk?.receive_configured ? 'green' : 'default'}>{dingtalk?.receive_configured ? '日报接收已配置' : '日报接收未配置'}</Tag>
              <Tag color={dingtalk?.openapi_configured ? 'green' : 'default'}>{dingtalk?.openapi_configured ? 'OpenAPI 已配置' : 'OpenAPI 未配置'}</Tag>
              <Tag color="geekblue">发送保护 20 条/分钟</Tag>
            </Space>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item label="发送通道" name="delivery_mode" initialValue="webhook">
                <Select
                  options={[
                    { value: 'webhook', label: 'Webhook 群机器人' },
                    { value: 'openapi', label: 'OpenAPI 应用机器人' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item label="钉钉消息接收地址">
                <Input
                  readOnly
                  value={`${typeof window !== 'undefined' ? window.location.origin : ''}${dingtalk?.callback_path || '/api/dingtalk/robot/callback'}`}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} md={16}>
              <Form.Item label="Webhook URL" name="webhook_url">
                <Input placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="Secret（SEC 加签密钥）" name="secret">
                <Input.Password placeholder="以 SEC 开头；留空则保留已配置密钥" />
              </Form.Item>
            </Col>
          </Row>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              应用凭证 · Client ID/Secret 用于接收机器人消息并获取官方接口令牌
              {dingtalk?.app_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
            </div>
            <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }}>
              主动推送到指定群还需要机器人编码和群会话 ID；旧应用 AgentId 只做应用身份记录，不等同于机器人编码。
            </Paragraph>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Client ID（原 AppKey）" name="app_key">
                <Input placeholder="钉钉应用 Client ID" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Client Secret（留空保留）" name="app_secret">
                <Input.Password placeholder="钉钉应用 Client Secret；留空则保留已配置密钥" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="应用 ID" name="app_id">
                <Input placeholder="钉钉应用 App ID" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="原企业内部应用 AgentId" name="agent_id">
                <Input placeholder="旧应用 AgentId，用于记录应用身份" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="机器人编码 RobotCode" name="robot_code">
                <Input placeholder="在应用机器人配置中查看，不是旧 AgentId" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="目标群会话 ID" name="open_conversation_id">
                <Input placeholder="openConversationId，用于主动推送到指定群" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="酷应用编码 CoolAppCode（可选）" name="cool_app_code">
                <Input placeholder="群聊酷应用编码，未使用可留空" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
        {dingtalk && (
          <div style={{ fontSize: 12 }}>
            <Text type="secondary">能力状态：</Text>
            <Space size={[4, 4]} wrap>
              {(dingtalk.capabilities || []).map((item: any) => (
                <Tag key={item.key} color={item.ready ? 'green' : 'default'}>{item.label}</Tag>
              ))}
            </Space>
          </div>
        )}
      </div>

      {/* 结构化标讯数据源配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><FileSearchOutlined /> 结构化标讯数据源配置</h3>
          <Button type="primary" onClick={handleSaveJianyu} size="small">保存配置</Button>
        </div>
        <Form form={jianyuForm} layout="vertical">
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              标讯采集 · 数据源账号与结构化数据 Key
              {dingtalk?.jianyu_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
              {dingtalk?.jianyu_api_key_masked && <Tag color="blue" style={{ marginLeft: 8 }}>Key {dingtalk.jianyu_api_key_masked}</Tag>}
            </div>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="手机号/账号" name="jianyu_username">
                <Input placeholder="数据源登录手机号" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="登录密码" name="jianyu_password">
                <Input.Password placeholder="留空则保留已配置密码" />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item label="结构化数据 Key" name="jianyu_api_key">
                <Input.Password placeholder="留空则保留已配置 Key；未配置时可用账号密码自动发现启用规则" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </div>

      {/* 系统信息 */}
      {sysInfo && (
        <div className="mgmt-section">
          <h3><ApiOutlined /> 系统信息</h3>
          <Descriptions size="small" bordered column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="版本">v{sysInfo.version}</Descriptions.Item>
            <Descriptions.Item label="LLM 模型">
              {sysInfo.llm_model}
              {sysInfo.llm_config_source && <Tag style={{ marginLeft: 8 }}>{sysInfo.llm_config_source === 'management' ? '管理中心配置' : '启动配置'}</Tag>}
            </Descriptions.Item>
            {Object.entries(sysInfo.data_stats || {}).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
            ))}
          </Descriptions>
        </div>
      )}
    </Spin>
  );
};

export default Management;
