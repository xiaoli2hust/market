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
import type { CrawlerRunLog, CrawlerSourceItem } from '@/services/api';
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

export const CrawlerRunsSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
    </>
  );
};
