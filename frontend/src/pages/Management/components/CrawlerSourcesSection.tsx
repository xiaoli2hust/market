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

export const CrawlerSourcesSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
    </>
  );
};
