import React, { useCallback, useEffect, useState } from 'react';
import { Form, Spin, message } from 'antd';
import dayjs from 'dayjs';
import {
  createCrawlerSource,
  deleteCrawlerSource,
  fetchCrawlerRuns,
  fetchCrawlerSources,
  fetchCrawlerStatus,
  fetchKeywords,
  fetchSchedule,
  getApiErrorMessage,
  triggerAllCrawlers,
  triggerCrawler,
  updateCrawlerSource,
  updateKeywords,
  updateSchedule,
  type CrawlerRunLog,
  type CrawlerSourceItem,
  type CrawlerStatus,
} from '@/services/api';
import {
  BIDDING_KEYWORDS_CONFIG,
  CATEGORY_LABELS,
  CRAWLER_MESSAGE_KEY,
  CRAWLER_RUN_STATUS_META,
  DIRECTION_KEYS,
  SOURCE_CATEGORY_ORDER,
  buildSourceSelectors,
  inferRiskLevelBySourceType,
  splitKeywordText,
} from './crawlerShared';
import { CrawlerEnginesSection } from './CrawlerEnginesSection';
import { CrawlerHealthSection } from './CrawlerHealthSection';
import { CrawlerKeywordsSection } from './CrawlerKeywordsSection';
import { CrawlerRunsSection } from './CrawlerRunsSection';
import { CrawlerScheduleSection } from './CrawlerScheduleSection';
import { CrawlerSourceModals } from './CrawlerSourceModals';
import { CrawlerSourcesSection } from './CrawlerSourcesSection';

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


  const ctx = {
    load,
    crawling,
    handleCrawlAll,
    crawlerHealthItems,
    sortedSources,
    sourceCategoryTab,
    setSourceCategoryTab,
    handleRunCrawler,
    crawlerStatus,
    scheduleForm,
    handleSaveSchedule,
    schedule,
    crawlerRuns,
    keywordTab,
    setKeywordTab,
    biddingSearchKeywordCount,
    biddingScoringKeywordCount,
    otherKeywordCount,
    biddingSearchKeywords,
    handleSaveKeywords,
    keywords,
    sourceCountByCategory,
    filteredSources,
    setAddModalVisible,
    handleToggleSource,
    openEditSource,
    handleDeleteSource,
    addModalVisible,
    handleAddSource,
    newSource,
    setNewSource,
    editingSource,
    setEditingSource,
    handleSaveSource,
    sourceForm,
  };

  return (
    <Spin spinning={loading}>
      <CrawlerHealthSection ctx={ctx} />
      <CrawlerEnginesSection ctx={ctx} />
      <CrawlerScheduleSection ctx={ctx} />
      <CrawlerRunsSection ctx={ctx} />
      <CrawlerKeywordsSection ctx={ctx} />
      <CrawlerSourcesSection ctx={ctx} />
      <CrawlerSourceModals ctx={ctx} />
    </Spin>
  );
};

export default CrawlerTab;
