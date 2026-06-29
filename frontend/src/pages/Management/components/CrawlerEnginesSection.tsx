import React from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { CrawlerRunLog, CrawlerSourceItem, CrawlerStatus } from '@/services/api';
import { WorkbenchSection, WorkbenchStatusRail } from '@/components/workbench';
import {
  BIDDING_KEYWORDS_CONFIG,
  CATEGORY_LABELS,
  CRAWLER_RUN_STATUS_META,
  DIRECTION_META,
  KEYWORD_CATEGORY_ORDER,
  SOURCE_CATEGORY_ORDER,
  SOURCE_RISK_OPTIONS,
  SOURCE_TYPE_LABELS,
  SOURCE_TYPE_OPTIONS,
  TARGET_SOURCE_CATEGORY_OPTIONS,
  formatDuration,
  inferRiskLevelBySourceType,
  sourceCapability,
  sourceRisk,
  sourceRiskTooltip,
  sourceRuleLabel,
  sourceRuntime,
  sourceStrategyStatus,
  sourceStrategyTooltip,
  sourceTier,
  sourceTypeColor,
  sourceTypeLabel,
  splitKeywordText,
  statusMeta,
} from './crawlerShared';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;
type CrawlerViewContext = Record<string, any>;

export const CrawlerEnginesSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
  const {
    load, crawling, handleCrawlAll, crawlerHealthItems, sortedSources, sourceCategoryTab,
    setSourceCategoryTab, handleRunCrawler, crawlerStatus, scheduleForm, handleSaveSchedule,
    schedule, crawlerRuns, keywordTab, setKeywordTab, biddingSearchKeywordCount,
    biddingScoringKeywordCount, otherKeywordCount, biddingSearchKeywords, handleSaveKeywords,
    keywords, sourceCountByCategory, filteredSources, setAddModalVisible, handleToggleSource,
    openEditSource, handleDeleteSource, addModalVisible, handleAddSource, newSource,
    setNewSource, editingSource, setEditingSource, handleSaveSource, sourceForm,
  } = ctx;

  return (
    <>
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
          {crawlerStatus.map((cs: CrawlerStatus) => {
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
                    {sourceDetails.length ? sourceDetails.slice(0, 3).map((source: any) => (
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
                    {sourceBreakdown.length ? sourceBreakdown.slice(0, 4).map((source: any) => (
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
    </>
  );
};
