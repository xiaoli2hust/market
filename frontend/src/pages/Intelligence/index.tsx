import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Space,
  Tabs,
  Tag,
  message,
} from 'antd';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FunnelPlotOutlined,
  RobotOutlined,
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
} from '@/components/workbench';
import {
  ModuleTab,
} from './components';
import {
  BiddingAgentView,
  CompetitorAgentView,
  IndustryKnowledgeAgentView,
  PolicyMarketAgentView,
} from './AgentViews';
import { DataCenterView } from './DataCenterView';
import {
  DATA_CATEGORY_OPTIONS,
  DataSortBy,
  DataSortOrder,
  INTELLIGENCE_CRAWLER_MESSAGE_KEY,
  PAGE_SIZE,
  formatWanAmount,
} from './intelligenceMeta';
import './intelligence.less';


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


  const intelligenceCtx = {
    analysisLoading,
    analysisPeriod,
    setAnalysisPeriod,
    openDataCenter,
    biddingAnalysis,
    policyAnalysis,
    marketAnalysis,
    competitorAnalysis,
    aiAnalysis,
    items,
    dataCategory,
    crawlerStatus,
    crawling,
    canRunAgents,
    dataCategoryOptions,
    searchValue,
    setSearchValue,
    handleSearch,
    handleCrawlAll,
    setDataCategory,
    setSortBy,
    setSortOrder,
    setPage,
    sortBy,
    sortOrder,
    loading,
    page,
    total,
    handleTableChange,
  };

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
            children: <BiddingAgentView ctx={intelligenceCtx} />,
          },
          {
            key: 'policy-market-agent',
            label: <ModuleTab no="02" title="政策与市场跟踪 Agent" desc="政策导向、市场信号、客户方向" />,
            children: <PolicyMarketAgentView ctx={intelligenceCtx} />,
          },
          {
            key: 'competitor-agent',
            label: <ModuleTab no="03" title="竞对监控 Agent" desc="中标、案例、产品与区域动作" />,
            children: <CompetitorAgentView ctx={intelligenceCtx} />,
          },
          {
            key: 'industry-knowledge-agent',
            label: <ModuleTab no="04" title="行业知识 Agent" desc="Agent、空间数据、方案素材" />,
            children: <IndustryKnowledgeAgentView ctx={intelligenceCtx} />,
          },
          {
            key: 'data-center',
            label: <ModuleTab no="05" title="市场数据采集中心" desc="标讯、政策、市场、竞对、知识库" />,
            children: <DataCenterView ctx={intelligenceCtx} />,
          },
        ]}
      />
    </div>
  );
};

export default Intelligence;
