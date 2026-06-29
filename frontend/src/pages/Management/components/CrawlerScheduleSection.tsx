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

export const CrawlerScheduleSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
    </>
  );
};
