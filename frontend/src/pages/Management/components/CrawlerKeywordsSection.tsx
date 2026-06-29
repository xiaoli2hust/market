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

export const CrawlerKeywordsSection: React.FC<{ ctx: CrawlerViewContext }> = ({ ctx }) => {
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
          <h3><FileSearchOutlined /> 关键词管理</h3>
          <Text type="secondary" style={{ fontSize: 12 }}>
            标讯搜索词 {biddingSearchKeywordCount} 个 · 标讯评分词 {biddingScoringKeywordCount} 个 · 政策/市场/竞对/行业知识 {otherKeywordCount} 个
          </Text>
        </div>

        <Tabs
          activeKey={keywordTab}
          onChange={setKeywordTab}
          size="small"
          items={[
            {
              key: 'bidding',
              label: <span><FileSearchOutlined /> 标讯</span>,
              children: (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      标讯召回词可直接编辑，分方向卡片用于核对业务口径；评分关键词用于采集后的匹配打分。
                    </Text>
                  </div>

                  <Card size="small" title="标讯召回关键词（可编辑）" style={{ marginBottom: 20 }}>
                    <TextArea
                      key={`bidding-keywords-${biddingSearchKeywords.join('|')}`}
                      defaultValue={biddingSearchKeywords.join(', ')}
                      rows={4}
                      placeholder="关键词用逗号或换行分隔"
                      onBlur={(e) => handleSaveKeywords('bidding', e.target.value)}
                    />
                  </Card>

                  {/* 搜索关键词 */}
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      分方向召回词参考
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.search).map(([dir, kws]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        return (
                          <Col key={dir} xs={24} md={12} lg={8}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{(kws as string[]).length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {(kws as string[]).map((kw: string, i: number) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>

                  {/* 评分关键词 */}
                  <div>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      评分关键词（采集后匹配打分使用）
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.scoring).map(([dir, kwStr]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        const kwList = splitKeywordText(kwStr as string);
                        return (
                          <Col key={dir} xs={24} md={12}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{kwList.length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {kwList.slice(0, 20).map((kw, i) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                                {kwList.length > 20 && (
                                  <Tag style={{ margin: '1px 2px', fontSize: 11, color: '#999' }}>+{kwList.length - 20} 个</Tag>
                                )}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>
                </div>
              ),
            },
            ...KEYWORD_CATEGORY_ORDER.map((category) => {
              const kw = keywords.find((item: { category: string; keywords: string[] }) => item.category === category) || { category, keywords: [] };
              const meta = CATEGORY_LABELS[category] || { label: category, color: 'default' };
              return {
                key: category,
                label: <span><GlobalOutlined /> {meta.label}关键词</span>,
                children: (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
                      {meta.label}采集使用的关键词。关键词用逗号或换行分隔，修改后离开输入框自动保存。
                    </Text>
                    <Card size="small" title={<Tag color={meta.color}>{meta.label}</Tag>}>
                      <TextArea
                        key={`keywords-${category}-${kw.keywords.join('|')}`}
                        defaultValue={kw.keywords.join(', ')}
                        rows={6}
                        placeholder="关键词用逗号或换行分隔"
                        onBlur={(e) => handleSaveKeywords(category, e.target.value)}
                      />
                    </Card>
                  </div>
                ),
              };
            }),
          ]}
        />
      </div>

    </>
  );
};
