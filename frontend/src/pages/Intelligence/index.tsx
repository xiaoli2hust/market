import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Input,
  Pagination,
  Row,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
  Tooltip,
} from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
  RobotOutlined,
  GlobalOutlined,
  EyeOutlined,
  FileSearchOutlined,
  ThunderboltOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchIntelligence,
  fetchIntelligenceStats,
  fetchCrawlerStatus,
  triggerAllCrawlers,
  IntelligenceItem,
  IntelligenceStats,
  CrawlerStatus,
} from '@/services/api';
import './intelligence.less';

const { Title, Paragraph, Text } = Typography;

const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  bidding: { label: '标讯信息', color: '#f5222d', icon: <FileSearchOutlined /> },
  news: { label: '市场动态', color: '#1890ff', icon: <GlobalOutlined /> },
  competitor: { label: '竞对监控', color: '#fa8c16', icon: <EyeOutlined /> },
  ai: { label: 'AI资讯', color: '#722ed1', icon: <RobotOutlined /> },
};

const PAGE_SIZE = 12;

const Intelligence: React.FC = () => {
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus[]>([]);
  const [tab, setTab] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchValue, setSearchValue] = useState('');

  /* -- Load data -- */
  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: PAGE_SIZE };
      if (tab !== 'all') params.category = tab;
      if (keyword) params.keyword = keyword;
      const resp = await fetchIntelligence(params);
      setItems(resp.items || []);
      setTotal(resp.total || 0);
    } catch {
      message.error('加载资讯列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, tab, keyword]);

  const loadStats = useCallback(async () => {
    try {
      const [s, cs] = await Promise.all([fetchIntelligenceStats(), fetchCrawlerStatus()]);
      setStats(s);
      setCrawlerStatus(cs);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadItems(); }, [loadItems]);
  useEffect(() => { loadStats(); }, []);

  /* -- Handlers -- */
  const handleSearch = () => {
    setKeyword(searchValue);
    setPage(1);
  };

  const handleTabChange = (key: string) => {
    setTab(key);
    setPage(1);
  };

  const handleCrawlAll = async () => {
    setCrawling(true);
    try {
      const results = await triggerAllCrawlers();
      const totalNew = results.reduce((sum, r) => sum + r.new_saved, 0);
      const totalFound = results.reduce((sum, r) => sum + r.total_found, 0);
      message.success(`爬取完成：发现 ${totalFound} 条，新增 ${totalNew} 条`);
      loadItems();
      loadStats();
    } catch {
      message.error('爬取失败，请稍后重试');
    } finally {
      setCrawling(false);
    }
  };

  const handleOpenLink = (url?: string) => {
    if (url) window.open(url, '_blank');
  };

  /* -- Stats cards data -- */
  const statCards = useMemo(() => {
    if (!stats) return [];
    return [
      { label: '总收录', value: stats.total, suffix: '条' },
      { label: '今日新增', value: stats.today_count, suffix: '条' },
      { label: '市场动态', value: stats.by_category?.news || 0, suffix: '条' },
      { label: '竞对监控', value: stats.by_category?.competitor || 0, suffix: '条' },
    ];
  }, [stats]);

  return (
    <div className="intel">
      {/* Headline */}
      <div className="intel-headline edl-rise edl-rise-1">
        <div className="intel-headline-left">
          <div className="edl-eyebrow">Intelligence Center · 情报中枢</div>
          <Title className="intel-title" level={1}>
            资讯<span className="accent">中心</span>
          </Title>
          <div className="intel-sub">
            行业标讯 · 市场动态 · 竞对监控 · AI前沿
            <span className="edl-mono"> · 共 {total} 条情报</span>
          </div>
        </div>
        <div className="intel-headline-right">
          <Tooltip title="一键爬取所有信息源">
            <Button
              type="primary"
              danger
              icon={<ThunderboltOutlined />}
              loading={crawling}
              onClick={handleCrawlAll}
              size="large"
            >
              一键采集
            </Button>
          </Tooltip>
        </div>
      </div>

      <hr className="edl-rule-strong" />

      {/* Stats Row */}
      <div className="intel-stats edl-rise edl-rise-2">
        <Row gutter={16}>
          {statCards.map((card, i) => (
            <Col key={i} span={6}>
              <div className="intel-stat-card">
                <div className="intel-stat-value">{card.value}</div>
                <div className="intel-stat-label">{card.label}</div>
              </div>
            </Col>
          ))}
        </Row>
      </div>

      {/* Crawler Status */}
      <div className="intel-crawler-bar edl-rise edl-rise-2">
        <div className="crawler-bar-label">
          <RobotOutlined /> 采集引擎
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
        >
          刷新采集
        </Button>
      </div>

      <hr className="edl-rule" />

      {/* Filters */}
      <div className="intel-filters edl-rise edl-rise-3">
        <Tabs
          activeKey={tab}
          onChange={handleTabChange}
          items={[
            { key: 'all', label: '全部' },
            { key: 'bidding', label: '标讯信息' },
            { key: 'news', label: '市场动态' },
            { key: 'competitor', label: '竞对监控' },
            { key: 'ai', label: 'AI资讯' },
          ]}
        />
        <Input.Search
          placeholder="搜索标题、摘要..."
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          style={{ width: 280 }}
          allowClear
        />
      </div>

      {/* Feed */}
      <Spin spinning={loading}>
        <div className="intel-feed edl-rise edl-rise-4">
          {items.length === 0 && !loading ? (
            <Empty description="暂无资讯数据" />
          ) : (
            <div className="intel-card-grid">
              {items.map((item) => {
                const meta = CATEGORY_META[item.category] || CATEGORY_META.news;
                return (
                  <div key={item.id} className="intel-card edl-card">
                    <div className="intel-card-head">
                      <Tag
                        color={meta.color}
                        icon={meta.icon}
                        className="intel-card-tag"
                      >
                        {meta.label}
                      </Tag>
                      {item.relevance_score != null && (
                        <span className="intel-card-score edl-mono">
                          {Math.round(item.relevance_score)}
                        </span>
                      )}
                    </div>
                    <div
                      className="intel-card-title"
                      onClick={() => handleOpenLink(item.source_url)}
                    >
                      {item.title}
                    </div>
                    <div className="intel-card-summary">
                      {item.summary || item.content?.slice(0, 120) || ''}
                    </div>
                    <div className="intel-card-foot">
                      <span className="intel-card-source">
                        {item.source || '—'}
                      </span>
                      <span className="intel-card-date edl-mono">
                        {item.published_at
                          ? dayjs(item.published_at).format('YYYY·MM·DD')
                          : '—'}
                      </span>
                      {item.source_url && (
                        <LinkOutlined
                          className="intel-card-link"
                          onClick={() => handleOpenLink(item.source_url)}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Spin>

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="intel-pagination">
          <Pagination
            current={page}
            pageSize={PAGE_SIZE}
            total={total}
            onChange={(p) => setPage(p)}
            showSizeChanger={false}
            showTotal={(t) => `共 ${t} 条`}
          />
        </div>
      )}
    </div>
  );
};

export default Intelligence;
