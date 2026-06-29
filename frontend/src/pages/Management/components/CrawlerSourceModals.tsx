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

export const CrawlerSourceModals: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
      {/* 添加站点 Modal */}
      <Modal title="添加目标站点" open={addModalVisible} onOk={handleAddSource} onCancel={() => setAddModalVisible(false)} okText="添加">
        <Form layout="vertical">
          <Form.Item label="分类">
            <Select value={newSource.category} onChange={v => setNewSource((s: any) => ({
              ...s,
              category: v,
              risk_level: inferRiskLevelBySourceType(s.source_type, v),
            }))}
              options={TARGET_SOURCE_CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item label="采集方式">
            <Select
              value={newSource.source_type}
              onChange={v => setNewSource((s: any) => ({
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
              onChange={v => setNewSource((s: any) => ({ ...s, risk_level: v }))}
              options={SOURCE_RISK_OPTIONS}
            />
          </Form.Item>
          <Form.Item label="名称" required>
            <Input value={newSource.name} onChange={e => setNewSource((s: any) => ({ ...s, name: e.target.value }))} placeholder="如：自然资源部" />
          </Form.Item>
          <Form.Item label="URL" required>
            <Input value={newSource.url} onChange={e => setNewSource((s: any) => ({ ...s, url: e.target.value }))} placeholder="https://..." />
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
    </>
  );
};
