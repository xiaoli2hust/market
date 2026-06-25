import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Empty,
  Input,
  Segmented,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  EyeOutlined,
  FileSearchOutlined,
  FunnelPlotOutlined,
  GlobalOutlined,
  LinkOutlined,
  ReloadOutlined,
  RobotOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  CrawlerStatus,
  IntelligenceAnalysis,
  IntelligenceItem,
  IntelligenceStats,
  OpportunityLeadStats,
  fetchCrawlerStatus,
  fetchIntelligence,
  fetchIntelligenceAnalysis,
  fetchIntelligenceStats,
  fetchOpportunityLeadStats,
  getApiErrorMessage,
  getCurrentUser,
  triggerAllCrawlers,
  userHasPermission,
} from '@/services/api';
import {
  WorkbenchMetricGrid,
  WorkbenchPageHeader,
  WorkbenchSection,
  WorkbenchStatusRail,
} from '@/components/workbench';
import {
  AgentSection,
  DistributionList,
  EvidenceRecordList,
  InsightPanel,
  MetricGrid,
  ModuleTab,
  TopSignalList,
} from './components';
import './intelligence.less';

const PAGE_SIZE = 12;
const INTELLIGENCE_CRAWLER_MESSAGE_KEY = 'intelligence-crawler-run';
type DataSortBy = 'published_at' | 'amount' | 'relevance' | 'created_at';
type DataSortOrder = 'asc' | 'desc';

const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  bidding: { label: '标讯数据', color: '#f5222d', icon: <FileSearchOutlined /> },
  policy: { label: '政策法规', color: '#13c2c2', icon: <GlobalOutlined /> },
  news: { label: '市场线索', color: '#1890ff', icon: <GlobalOutlined /> },
  competitor: { label: '竞对监控', color: '#fa8c16', icon: <EyeOutlined /> },
  ai: { label: '行业知识', color: '#722ed1', icon: <RobotOutlined /> },
};

const DATA_CATEGORY_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'bidding', label: '标讯' },
  { value: 'policy', label: '政策' },
  { value: 'news', label: '市场' },
  { value: 'competitor', label: '竞对' },
  { value: 'ai', label: '行业知识' },
];

const formatWanAmount = (amount?: number) => {
  const value = Number(amount || 0);
  if (!value) return '0万';
  if (value >= 10000) return `${(value / 10000).toFixed(2)}亿`;
  if (value >= 100) return `${value.toFixed(1)}万`;
  return `${value.toFixed(2)}万`;
};

const itemAmountWan = (item: IntelligenceItem) => Number(item.amount_wan ?? item.extra_data?.amount_wan ?? 0);

const itemAmountText = (item: IntelligenceItem) => {
  const explicit = item.amount_display || item.extra_data?.amount_display;
  if (explicit) return String(explicit);
  const amount = itemAmountWan(item);
  return amount > 0 ? formatWanAmount(amount) : '—';
};

const itemSourceText = (item: IntelligenceItem) => (
  item.category === 'bidding' ? '标讯数据' : item.source || item.extra_data?.source || '外部信号'
);

const tableSortOrder = (active: boolean, order: DataSortOrder) => (
  active ? (order === 'asc' ? 'ascend' : 'descend') : undefined
) as 'ascend' | 'descend' | undefined;

const uniqueTexts = (...groups: Array<string[] | undefined>) => {
  const seen = new Set<string>();
  const result: string[] = [];
  groups.flat().forEach((text) => {
    const value = String(text || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result;
};

const Intelligence: React.FC = () => {
  const currentUser = getCurrentUser();
  const canRunAgents = userHasPermission(currentUser, 'management:crawler');
  const [moduleKey, setModuleKey] = useState('bidding-agent');
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [leadStats, setLeadStats] = useState<OpportunityLeadStats | null>(null);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus[]>([]);
  const [biddingAnalysis, setBiddingAnalysis] = useState<IntelligenceAnalysis | null>(null);
  const [policyAnalysis, setPolicyAnalysis] = useState<IntelligenceAnalysis | null>(null);
  const [marketAnalysis, setMarketAnalysis] = useState<IntelligenceAnalysis | null>(null);
  const [competitorAnalysis, setCompetitorAnalysis] = useState<IntelligenceAnalysis | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<IntelligenceAnalysis | null>(null);
  const [analysisPeriod, setAnalysisPeriod] = useState<'week' | 'month'>('month');
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [dataCategory, setDataCategory] = useState('all');
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [sortBy, setSortBy] = useState<DataSortBy>('published_at');
  const [sortOrder, setSortOrder] = useState<DataSortOrder>('desc');

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: PAGE_SIZE, sort_by: sortBy, sort_order: sortOrder };
      if (dataCategory !== 'all') params.category = dataCategory;
      if (keyword) params.keyword = keyword;
      const resp = await fetchIntelligence(params);
      setItems(resp.items || []);
      setTotal(resp.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载市场数据失败'));
    } finally {
      setLoading(false);
    }
  }, [page, dataCategory, keyword, sortBy, sortOrder]);

  const loadStats = useCallback(async () => {
    try {
      const [s, cs, ls] = await Promise.all([
        fetchIntelligenceStats(),
        fetchCrawlerStatus(),
        fetchOpportunityLeadStats().catch(() => null),
      ]);
      setStats(s);
      setCrawlerStatus(cs);
      setLeadStats(ls);
    } catch {
      // 静默处理，页面主体可继续展示。
    }
  }, []);

  const loadAnalysis = useCallback(async () => {
    setAnalysisLoading(true);
    try {
      const [bidding, policy, market, competitor, ai] = await Promise.all([
        fetchIntelligenceAnalysis({ category: 'bidding', period: analysisPeriod }),
        fetchIntelligenceAnalysis({ category: 'policy', period: analysisPeriod }),
        fetchIntelligenceAnalysis({ category: 'news', period: analysisPeriod }),
        fetchIntelligenceAnalysis({ category: 'competitor', period: analysisPeriod }),
        fetchIntelligenceAnalysis({ category: 'ai', period: analysisPeriod }),
      ]);
      setBiddingAnalysis(bidding);
      setPolicyAnalysis(policy);
      setMarketAnalysis(market);
      setCompetitorAnalysis(competitor);
      setAiAnalysis(ai);
    } catch {
      setBiddingAnalysis(null);
      setPolicyAnalysis(null);
      setMarketAnalysis(null);
      setCompetitorAnalysis(null);
      setAiAnalysis(null);
    } finally {
      setAnalysisLoading(false);
    }
  }, [analysisPeriod]);

  useEffect(() => { loadItems(); }, [loadItems]);
  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadAnalysis(); }, [loadAnalysis]);

  const handleCrawlAll = async () => {
    setCrawling(true);
    message.open({
      key: INTELLIGENCE_CRAWLER_MESSAGE_KEY,
      type: 'loading',
      content: '正在运行市场洞察 Agent，公开网站会按反爬策略低频采集',
      duration: 0,
    });
    try {
      const results = await triggerAllCrawlers();
      const totalNew = results.reduce((sum, r) => sum + r.new_saved, 0);
      const totalFound = results.reduce((sum, r) => sum + r.total_found, 0);
      message.success({
        key: INTELLIGENCE_CRAWLER_MESSAGE_KEY,
        content: `Agent 运行完成：发现 ${totalFound} 条，新增 ${totalNew} 条`,
      });
      await Promise.all([loadItems(), loadStats(), loadAnalysis()]);
    } catch (e: any) {
      message.error({
        key: INTELLIGENCE_CRAWLER_MESSAGE_KEY,
        content: getApiErrorMessage(e, 'Agent 运行失败，请稍后重试'),
      });
    } finally {
      setCrawling(false);
    }
  };

  const handleSearch = () => {
    setKeyword(searchValue);
    setPage(1);
  };

  const openDataCenter = (category: string) => {
    setDataCategory(category);
    setPage(1);
    setSortBy(category === 'bidding' ? 'amount' : 'published_at');
    setSortOrder('desc');
    setModuleKey('data-center');
  };

  const statCards = useMemo(() => [
    { label: '入库信号', value: stats?.total || 0, suffix: '条', icon: <DatabaseOutlined />, tone: 'blue' as const },
    { label: '标讯数据', value: stats?.by_category?.bidding || 0, suffix: '条', icon: <FileSearchOutlined />, tone: 'red' as const },
    { label: '高价值待看', value: leadStats?.actionable_count || 0, suffix: '条', icon: <FunnelPlotOutlined />, tone: 'gold' as const },
    { label: '识别金额', value: formatWanAmount(biddingAnalysis?.summary.amount_total_wan), suffix: '', icon: <CheckCircleOutlined />, tone: 'green' as const },
  ], [stats, leadStats, biddingAnalysis]);

  const dataCategoryOptions = useMemo(() => DATA_CATEGORY_OPTIONS.map((option) => {
    const count = option.value === 'all'
      ? stats?.total || 0
      : stats?.by_category?.[option.value] || 0;
    return {
      value: option.value,
      label: `${option.label} ${count}`,
    };
  }), [stats]);

  const agentCommandCards = useMemo(() => ([
    {
      key: 'bidding-agent',
      no: '01',
      title: '标讯雷达',
      count: biddingAnalysis?.summary.relevant || 0,
      label: '高相关标讯',
      insight: biddingAnalysis?.findings?.[0] || '等待标讯分析结果形成行业、金额和关键词判断。',
      action: biddingAnalysis?.recommendations?.[0] || '先运行采集并进入数据采集中心核对来源质量。',
      status: biddingAnalysis ? 'good' : 'muted',
    },
    {
      key: 'policy-market-agent',
      no: '02',
      title: '政策与市场',
      count: (policyAnalysis?.summary.relevant || 0) + (marketAnalysis?.summary.relevant || 0),
      label: '导向信号',
      insight: policyAnalysis?.findings?.[0] || marketAnalysis?.findings?.[0] || '等待政策与市场信号形成客户方向判断。',
      action: policyAnalysis?.recommendations?.[0] || marketAnalysis?.recommendations?.[0] || '补充政策和市场来源后再观察导向。',
      status: policyAnalysis || marketAnalysis ? 'good' : 'muted',
    },
    {
      key: 'competitor-agent',
      no: '03',
      title: '竞对监控',
      count: competitorAnalysis?.summary.relevant || 0,
      label: '竞对动作',
      insight: competitorAnalysis?.findings?.[0] || '等待竞对中标、案例和产品动作形成判断。',
      action: competitorAnalysis?.recommendations?.[0] || '补齐竞对来源并关注武大吉奥、京东舆图、海致等重点对象。',
      status: competitorAnalysis ? 'warn' : 'muted',
    },
    {
      key: 'industry-knowledge-agent',
      no: '04',
      title: '行业知识',
      count: aiAnalysis?.summary.relevant || 0,
      label: '知识素材',
      insight: aiAnalysis?.findings?.[0] || '等待 Agent、空间数据、地址治理等知识素材沉淀。',
      action: aiAnalysis?.recommendations?.[0] || '持续补充空间数据、GIS、Agent 和行业动态来源。',
      status: aiAnalysis ? 'good' : 'muted',
    },
  ]), [biddingAnalysis, policyAnalysis, marketAnalysis, competitorAnalysis, aiAnalysis]);

  const dataQualityStats = useMemo(() => {
    const withDate = items.filter((item) => !!item.published_at).length;
    const withAmount = items.filter((item) => itemAmountWan(item) > 0).length;
    const withSource = items.filter((item) => !!item.source_url).length;
    return [
      { label: '当前页', value: `${items.length} 条`, status: items.length ? 'good' as const : 'muted' as const },
      { label: '有发布日期', value: `${withDate} 条`, meta: `${items.length ? Math.round((withDate / items.length) * 100) : 0}%`, status: withDate ? 'good' as const : 'warn' as const },
      { label: '有金额', value: `${withAmount} 条`, meta: dataCategory === 'bidding' ? '标讯重点字段' : '非标讯可为空', status: withAmount ? 'good' as const : 'warn' as const },
      { label: '可追溯原文', value: `${withSource} 条`, status: withSource ? 'good' as const : 'warn' as const },
    ];
  }, [items, dataCategory]);

  const dataColumns = useMemo(() => [
    {
      title: '信号',
      dataIndex: 'title',
      key: 'title',
      render: (_: string, item: IntelligenceItem) => {
        const meta = CATEGORY_META[item.category] || CATEGORY_META.news;
        const keywords = item.extra_data?.matched_keywords || [];
        return (
          <div className="intel-data-title">
            <div>
              <Tag color={meta.color} icon={meta.icon}>{meta.label}</Tag>
              <strong onClick={() => item.source_url && window.open(item.source_url, '_blank', 'noopener,noreferrer')}>{item.title}</strong>
            </div>
            {(item.summary || item.content) && <p>{item.summary || item.content?.slice(0, 120)}</p>}
            {!!keywords.length && (
              <div className="intel-data-keywords">
                {keywords.slice(0, 4).map((kw: string) => <Tag key={kw}>{kw}</Tag>)}
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: '发布日期',
      dataIndex: 'published_at',
      key: 'published_at',
      width: 124,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'published_at', sortOrder),
      render: (_: string, item: IntelligenceItem) => (
        <div className="intel-data-date">
          <strong>{item.published_at ? dayjs(item.published_at).format('YYYY-MM-DD') : '未标日期'}</strong>
          {!item.published_at && item.created_at && <span>入库 {dayjs(item.created_at).format('MM-DD')}</span>}
        </div>
      ),
    },
    {
      title: '金额',
      dataIndex: 'amount_wan',
      key: 'amount_wan',
      width: 112,
      align: 'right' as const,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'amount', sortOrder),
      render: (_: number, item: IntelligenceItem) => (
        <span className={itemAmountWan(item) > 0 ? 'intel-data-amount strong' : 'intel-data-amount'}>
          {itemAmountText(item)}
        </span>
      ),
    },
    {
      title: '相关度',
      dataIndex: 'relevance_score',
      key: 'relevance_score',
      width: 96,
      align: 'right' as const,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'relevance', sortOrder),
      render: (score?: number) => (score == null ? '—' : <span className="edl-mono">{Math.round(score)}</span>),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 170,
      render: (_: string, item: IntelligenceItem) => (
        <div className="intel-data-source">
          <span>{itemSourceText(item)}</span>
          {item.source_url && <LinkOutlined onClick={() => window.open(item.source_url, '_blank', 'noopener,noreferrer')} />}
        </div>
      ),
    },
  ], [sortBy, sortOrder]);

  const handleTableChange = (pagination: any, _: any, sorter: any) => {
    const activeSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    const nextPage = Number(pagination?.current || 1);
    setPage(nextPage);
    if (!activeSorter?.order) {
      setSortBy('published_at');
      setSortOrder('desc');
      return;
    }
    const field = String(activeSorter.field || activeSorter.columnKey || '');
    const fieldMap: Record<string, DataSortBy> = {
      published_at: 'published_at',
      amount_wan: 'amount',
      relevance_score: 'relevance',
      created_at: 'created_at',
    };
    setSortBy(fieldMap[field] || 'published_at');
    setSortOrder(activeSorter.order === 'ascend' ? 'asc' : 'desc');
  };

  const renderBiddingAgent = () => (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Bidding Radar Agent"
        title="标讯雷达 Agent"
        desc="不是把标讯堆给销售，而是先判断哪些值得关注、集中在哪些行业场景、由哪些关键词触发。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<FileSearchOutlined />} onClick={() => openDataCenter('bidding')}>
              标讯雷达明细
            </Button>
          </Space>
        )}
      >
        {biddingAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效标讯', biddingAnalysis.summary.relevant, '条'],
                ['平均贴合度', biddingAnalysis.summary.avg_score, '分'],
                ['识别金额', formatWanAmount(biddingAnalysis.summary.amount_total_wan), ''],
                ['过滤噪音', biddingAnalysis.summary.ignored, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="当前判断">
                {(biddingAnalysis.findings || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="建议动作">
                {(biddingAnalysis.recommendations || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="行业/场景分布">
                <DistributionList items={biddingAnalysis.distribution.topics} tone="red" />
                <DistributionList items={biddingAnalysis.distribution.customer_types} />
              </InsightPanel>
              <InsightPanel title="关键词触发分布">
                <DistributionList items={biddingAnalysis.distribution.keywords || []} tone="red" />
              </InsightPanel>
            </div>
            <TopSignalList
              title="高贴合标讯关注"
              items={biddingAnalysis.top_items || []}
              emptyText="暂无高贴合标讯"
              onOpenData={() => openDataCenter('bidding')}
            />
            <EvidenceRecordList
              title="分析证据记录"
              items={biddingAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('bidding')}
            />
          </>
        ) : (
          <Empty description="暂无标讯分析数据" />
        )}
      </AgentSection>
    </Spin>
  );

  const renderPolicyMarketAgent = () => {
    const recommendations = uniqueTexts(policyAnalysis?.recommendations, marketAnalysis?.recommendations);
    const findings = uniqueTexts(policyAnalysis?.findings, marketAnalysis?.findings);
    return (
      <Spin spinning={analysisLoading}>
        <AgentSection
          eyebrow="Policy & Market Tracking Agent"
          title="政策与市场跟踪 Agent"
          desc="只分析高相关政策和市场线索，回答市场导向、客户方向和应该沉淀成什么打法。"
          actions={(
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
          )}
        >
          <MetricGrid
            metrics={[
              ['高相关政策', policyAnalysis?.summary.relevant || 0, '条'],
              ['市场线索', marketAnalysis?.summary.relevant || 0, '条'],
              ['政策评分', policyAnalysis?.summary.avg_score || 0, '分'],
              ['市场评分', marketAnalysis?.summary.avg_score || 0, '分'],
            ]}
          />
          <div className="intel-agent-grid">
            <InsightPanel title="市场导向">
              {findings.length ? findings.slice(0, 5).map((text) => <p key={text}>{text}</p>) : <p>暂无高相关政策与市场信号。</p>}
            </InsightPanel>
            <InsightPanel title="Agent 建议">
              {recommendations.length ? recommendations.slice(0, 5).map((text) => <p key={text}>{text}</p>) : <p>先补充政策和市场采集源，再形成导向判断。</p>}
            </InsightPanel>
            <InsightPanel title="政策主题">
              <DistributionList items={policyAnalysis?.distribution.topics || []} tone="cyan" />
            </InsightPanel>
            <InsightPanel title="市场关键词">
              <DistributionList items={marketAnalysis?.distribution.keywords || []} />
            </InsightPanel>
          </div>
          <TopSignalList
            title="重点政策与市场信号"
            items={[...(policyAnalysis?.top_items || []), ...(marketAnalysis?.top_items || [])].slice(0, 8)}
            emptyText="暂无重点政策或市场信号"
            onOpenData={() => openDataCenter('policy')}
          />
          <EvidenceRecordList
            title="导向判断证据"
            items={[...(policyAnalysis?.evidence_records || []), ...(marketAnalysis?.evidence_records || [])].slice(0, 12)}
            onOpenData={() => openDataCenter('policy')}
          />
        </AgentSection>
      </Spin>
    );
  };

  const renderCompetitorAgent = () => (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Competitor Monitoring Agent"
        title="竞对监控 Agent"
        desc="围绕竞对中标、重点客户案例、产品动作和区域推进做研判，输出应该关注什么、如何调整打法。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<EyeOutlined />} onClick={() => openDataCenter('competitor')}>
              竞对信号明细
            </Button>
          </Space>
        )}
      >
        {competitorAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效竞对信号', competitorAnalysis.summary.relevant, '条'],
                ['平均影响评分', competitorAnalysis.summary.avg_score, '分'],
                ['动作类型', competitorAnalysis.distribution.actions.length, '类'],
                ['证据记录', competitorAnalysis.summary.evidence_count || 0, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="竞对判断">
                {(competitorAnalysis.findings || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="建议动作">
                {(competitorAnalysis.recommendations || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="竞对主题">
                <DistributionList items={competitorAnalysis.distribution.topics || []} />
              </InsightPanel>
              <InsightPanel title="客户与区域">
                <DistributionList items={competitorAnalysis.distribution.customer_types || []} />
                <DistributionList items={competitorAnalysis.distribution.regions || []} />
              </InsightPanel>
            </div>
            <TopSignalList
              title="重点竞对动作"
              items={competitorAnalysis.top_items || []}
              emptyText="暂无重点竞对信号"
              onOpenData={() => openDataCenter('competitor')}
            />
            <EvidenceRecordList
              title="竞对判断证据"
              items={competitorAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('competitor')}
            />
          </>
        ) : (
          <Empty description="暂无竞对分析数据" />
        )}
      </AgentSection>
    </Spin>
  );

  const renderIndustryKnowledgeAgent = () => (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Industry Knowledge Agent"
        title="行业知识 Agent"
        desc="沉淀 Agent、空间数据、GIS、地址治理、数据治理和行业技术动态，用于售前话术、方案素材和产品方向判断。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<RobotOutlined />} onClick={() => openDataCenter('ai')}>
              知识素材明细
            </Button>
          </Space>
        )}
      >
        {aiAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效知识素材', aiAnalysis.summary.relevant, '条'],
                ['平均相关度', aiAnalysis.summary.avg_score, '分'],
                ['主题数量', aiAnalysis.distribution.topics.length, '类'],
                ['证据记录', aiAnalysis.summary.evidence_count || 0, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="知识判断">
                {(aiAnalysis.findings || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="沉淀建议">
                {(aiAnalysis.recommendations || []).map((text) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="主题分布">
                <DistributionList items={aiAnalysis.distribution.topics || []} />
              </InsightPanel>
              <InsightPanel title="关键词与动作">
                <DistributionList items={aiAnalysis.distribution.keywords || []} />
                <DistributionList items={aiAnalysis.distribution.actions || []} />
              </InsightPanel>
            </div>
            <TopSignalList
              title="重点知识素材"
              items={aiAnalysis.top_items || []}
              emptyText="暂无重点行业知识"
              onOpenData={() => openDataCenter('ai')}
            />
            <EvidenceRecordList
              title="知识判断证据"
              items={aiAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('ai')}
            />
          </>
        ) : (
          <Empty description="暂无行业知识分析数据" />
        )}
      </AgentSection>
    </Spin>
  );

  const renderDataCenter = () => (
    <div className="intel-data-center">
      <div className="intel-crawler-bar">
        <div className="crawler-bar-label">
          <RobotOutlined /> 采集状态
        </div>
        <div className="crawler-bar-items">
          {crawlerStatus.map((cs) => (
            <div key={cs.name} className="crawler-bar-item">
              <span className="crawler-dot" data-status={cs.status} />
              <span className="crawler-name">{cs.label}</span>
              <span className="crawler-count edl-mono">{cs.total_collected}</span>
            </div>
          ))}
        </div>
        <Button
          icon={<ReloadOutlined spin={crawling} />}
          size="small"
          onClick={handleCrawlAll}
          loading={crawling}
          disabled={!canRunAgents}
          title={!canRunAgents ? '当前账号无采集管理权限' : undefined}
        >
          重新采集
        </Button>
      </div>

      <div className="intel-data-toolbar">
        <div className="intel-type-switch">
          <span>数据类型</span>
          <Segmented
            value={dataCategory}
            onChange={(key) => {
              const nextCategory = String(key);
              setDataCategory(nextCategory);
              setSortBy(nextCategory === 'bidding' ? 'amount' : 'published_at');
              setSortOrder('desc');
              setPage(1);
            }}
            options={dataCategoryOptions}
          />
        </div>
        <Segmented
          className="intel-data-sort"
          value={`${sortBy}:${sortOrder}`}
          onChange={(value) => {
            const [nextSortBy, nextSortOrder] = String(value).split(':') as [DataSortBy, DataSortOrder];
            setSortBy(nextSortBy);
            setSortOrder(nextSortOrder);
            setPage(1);
          }}
          options={[
            { label: '最新优先', value: 'published_at:desc' },
            { label: '金额最高', value: 'amount:desc' },
            { label: '相关度最高', value: 'relevance:desc' },
          ]}
        />
        <Input.Search
          className="intel-data-search"
          placeholder="搜索标题、摘要..."
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          allowClear
          />
        </div>

      <WorkbenchStatusRail items={dataQualityStats} />

      <Table<IntelligenceItem>
        className="intel-data-table"
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={dataColumns}
        scroll={{ x: 820 }}
        onChange={handleTableChange}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          showSizeChanger: false,
          showTotal: (count) => `共 ${count} 条`,
        }}
        locale={{ emptyText: <Empty description="暂无市场数据" /> }}
      />
    </div>
  );

  return (
    <div className="intel">
      <WorkbenchPageHeader
        eyebrow="Market Insight"
        title="市场"
        accent="洞察"
        description={(
          <>
            标讯雷达 Agent · 政策与市场跟踪 Agent · 竞对监控 Agent · 行业知识 Agent · 市场数据采集中心
            <span className="edl-mono"> · 共 {stats?.total || total} 条信号</span>
          </>
        )}
        actions={[{
          label: crawling ? 'Agent 运行中...' : '运行全部 Agent',
          type: 'primary',
          danger: true,
          icon: <ThunderboltOutlined />,
          loading: crawling,
          disabled: !canRunAgents,
          title: !canRunAgents ? '当前账号无采集管理权限' : undefined,
          onClick: handleCrawlAll,
          size: 'large',
        }]}
      />
      {crawling && (
        <div className="intel-crawler-running">
          <ThunderboltOutlined />
          <span>正在逐源采集、去重和分析，公开网站会按反爬策略低频访问，请等待结果返回。</span>
        </div>
      )}

      <WorkbenchMetricGrid metrics={statCards} />

      <WorkbenchSection
        title="Agent 本期判断"
        description="先看每个 Agent 给出的结论、建议动作和证据入口，再决定是否进入明细表。"
        className="intel-command-section"
      >
        <div className="intel-agent-command">
          {agentCommandCards.map((agent) => (
            <button key={agent.key} type="button" onClick={() => setModuleKey(agent.key)}>
              <div>
                <span className="edl-mono">{agent.no}</span>
                <Tag color={agent.status === 'good' ? 'green' : agent.status === 'warn' ? 'orange' : 'default'}>
                  {agent.count} {agent.label}
                </Tag>
              </div>
              <strong>{agent.title}</strong>
              <p>{agent.insight}</p>
              <em>{agent.action}</em>
            </button>
          ))}
        </div>
      </WorkbenchSection>

      <Tabs
        className="intel-module-tabs edl-rise edl-rise-2"
        tabPosition="left"
        activeKey={moduleKey}
        onChange={setModuleKey}
        items={[
          {
            key: 'bidding-agent',
            label: <ModuleTab no="01" title="标讯雷达 Agent" desc="贴合度、金额、行业与关键词" />,
            children: renderBiddingAgent(),
          },
          {
            key: 'policy-market-agent',
            label: <ModuleTab no="02" title="政策与市场跟踪 Agent" desc="政策导向、市场信号、客户方向" />,
            children: renderPolicyMarketAgent(),
          },
          {
            key: 'competitor-agent',
            label: <ModuleTab no="03" title="竞对监控 Agent" desc="中标、案例、产品与区域动作" />,
            children: renderCompetitorAgent(),
          },
          {
            key: 'industry-knowledge-agent',
            label: <ModuleTab no="04" title="行业知识 Agent" desc="Agent、空间数据、方案素材" />,
            children: renderIndustryKnowledgeAgent(),
          },
          {
            key: 'data-center',
            label: <ModuleTab no="05" title="市场数据采集中心" desc="标讯、政策、市场、竞对、知识库" />,
            children: renderDataCenter(),
          },
        ]}
      />
    </div>
  );
};

export default Intelligence;
