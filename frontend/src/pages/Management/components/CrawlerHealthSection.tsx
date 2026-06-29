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

export const CrawlerHealthSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
            const categorySources = sortedSources.filter((source: CrawlerSourceItem) => source.category === category);
            const categoryActive = categorySources.filter((source: CrawlerSourceItem) => source.is_active).length;
            const categoryIssue = categorySources.filter((source: CrawlerSourceItem) => source.strategy_status === 'needs_rules' || source.runtime_status === 'blocked' || source.runtime_status === 'error').length;
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
    </>
  );
};
