import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  message,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { history } from '@@/exports';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CompassOutlined,
  LinkOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  discoverOpportunityLeads,
  fetchOpportunityLeads,
  fetchOpportunityLeadStats,
  OpportunityDecision,
  OpportunityLead,
  OpportunityLeadStats,
  OpportunityStatus,
  getApiErrorMessage,
  getCurrentUser,
  updateOpportunityLeadStatus,
  userHasPermission,
} from '@/services/api';
import './opportunities.less';

const { Title } = Typography;

const DECISION_META: Record<OpportunityDecision, { label: string; color: string; tone: string }> = {
  HIGH_PRIORITY: { label: '重点跟进', color: 'red', tone: 'hot' },
  MEDIUM: { label: '建议跟进', color: 'orange', tone: 'warm' },
  LOW: { label: '观察', color: 'blue', tone: 'cool' },
  IGNORE: { label: '暂缓', color: 'default', tone: 'quiet' },
};

const STATUS_META: Record<OpportunityStatus, { label: string; color: string }> = {
  new: { label: '新线索', color: 'blue' },
  reviewing: { label: '评估中', color: 'orange' },
  converted: { label: '已确认', color: 'green' },
  ignored: { label: '已忽略', color: 'default' },
};

const formatBudget = (value: number) => {
  if (!value) return '未披露';
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  return `${(value / 10000).toFixed(1)}万`;
};

const OpportunityRadar: React.FC = () => {
  const currentUser = getCurrentUser();
  const canManageLeads = userHasPermission(currentUser, 'opportunities:manage');
  const [items, setItems] = useState<OpportunityLead[]>([]);
  const [stats, setStats] = useState<OpportunityLeadStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [decision, setDecision] = useState<string>();
  const [status, setStatus] = useState<string>();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const loadData = async (nextPage = page, nextPageSize = pageSize) => {
    setLoading(true);
    try {
      const [listResp, statsResp] = await Promise.all([
        fetchOpportunityLeads({
          decision,
          status,
          keyword: keyword || undefined,
          page: nextPage,
          page_size: nextPageSize,
        }),
        fetchOpportunityLeadStats(),
      ]);
      setItems(listResp.items || []);
      setTotal(listResp.total || 0);
      setStats(statsResp);
      setPage(nextPage);
      setPageSize(nextPageSize);
    } catch (err: any) {
      message.error(getApiErrorMessage(err, '线索数据加载失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(1, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decision, status]);

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const resp = await discoverOpportunityLeads({ pages_per_source: 4, persist: true });
      message.success(`发现 ${resp.total} 条标讯线索，新增 ${resp.saved} 条，更新 ${resp.updated} 条`);
      await loadData(1, pageSize);
    } catch (err: any) {
      message.error(getApiErrorMessage(err, '抓取分析失败'));
    } finally {
      setDiscovering(false);
    }
  };

  const handleStatusChange = async (id: number, nextStatus: OpportunityStatus) => {
    try {
      await updateOpportunityLeadStatus(id, nextStatus);
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: nextStatus } : item)));
      message.success('状态已更新');
    } catch (err: any) {
      message.error(getApiErrorMessage(err, '状态更新失败'));
    }
  };

  const decisionOptions = useMemo(
    () => [
      { value: '', label: '全部优先级' },
      ...Object.entries(DECISION_META).map(([value, meta]) => ({
        value,
        label: `${meta.label} ${stats?.by_decision?.[value] || 0}`,
      })),
    ],
    [stats],
  );

  const columns: ColumnsType<OpportunityLead> = [
    {
      title: '线索',
      dataIndex: 'project_name',
      render: (_, record) => (
        <div className="opp-lead-title">
          <div className="opp-project">{record.project_name}</div>
          <div className="opp-meta">
            <span>{record.buyer || '采购单位未披露'}</span>
            <span>{record.procurement_method || '公告'}</span>
            <span>{record.publish_date ? dayjs(record.publish_date).format('YYYY.MM.DD') : '日期未知'}</span>
          </div>
        </div>
      ),
    },
    {
      title: '预算',
      dataIndex: 'budget',
      width: 110,
      sorter: (a, b) => a.budget - b.budget,
      render: (value: number) => <span className="opp-budget edl-mono">{formatBudget(value)}</span>,
    },
    {
      title: '评分',
      dataIndex: 'score',
      width: 120,
      sorter: (a, b) => a.score - b.score,
      render: (value: number, record) => (
        <div className="opp-score">
          <Progress percent={value} size="small" showInfo={false} strokeColor={value >= 80 ? '#C53A2C' : '#C77A2E'} />
          <span className="edl-mono">{value}</span>
          <Tag color={DECISION_META[record.decision]?.color || 'default'}>{DECISION_META[record.decision]?.label}</Tag>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 130,
      render: (value: OpportunityStatus, record) => (
        <Select
          size="small"
          value={value}
          style={{ width: 104 }}
          disabled={!canManageLeads}
          onChange={(next) => handleStatusChange(record.id, next)}
          options={Object.entries(STATUS_META).map(([key, meta]) => ({
            value: key,
            label: meta.label,
          }))}
        />
      ),
    },
    {
      title: '动作',
      width: 168,
      render: (_, record) => (
        <Space size={6}>
          <Button size="small" icon={<LinkOutlined />} onClick={() => window.open(record.url, '_blank', 'noopener,noreferrer')}>
            原文
          </Button>
          <Button
            size="small"
            type={record.status === 'converted' ? 'default' : 'primary'}
            icon={<CheckCircleOutlined />}
            disabled={record.status === 'converted' || !canManageLeads}
            title={!canManageLeads ? '当前账号无线索确认权限' : undefined}
            onClick={() => handleStatusChange(record.id, 'converted')}
          >
            {record.status === 'converted' ? '已确认' : '确认线索'}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="opp">
      <div className="opp-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">Bidding Lead Review · 标讯线索确认</div>
          <Title className="opp-title" level={1}>
            标讯<span className="accent">线索确认</span>
          </Title>
          <div className="opp-sub">
            基于标讯分析结果 · 人工确认价值 · 确认后进入商机中心证据区
          </div>
        </div>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => history.push('/intelligence')}>
            市场洞察
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => loadData(1, pageSize)} loading={loading}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<RadarChartOutlined />}
            onClick={handleDiscover}
            loading={discovering}
            disabled={!canManageLeads}
            title={!canManageLeads ? '当前账号无线索分析权限' : undefined}
          >
            刷新线索评分
          </Button>
        </Space>
      </div>

      <hr className="edl-rule-strong" />

      <Row className="opp-stats edl-rise edl-rise-2" gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><CompassOutlined /> 总线索</div>
            <div className="opp-stat-value"><span className="edl-display">{stats?.total || 0}</span><span>条</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><ThunderboltOutlined /> 可行动</div>
            <div className="opp-stat-value"><span className="edl-display">{stats?.actionable_count || 0}</span><span>条</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><CheckCircleOutlined /> 预算池</div>
            <div className="opp-stat-value"><span className="edl-display">{formatBudget(stats?.budget_total || 0)}</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><ClockCircleOutlined /> 最近更新</div>
            <div className="opp-stat-value opp-stat-date">
              {stats?.latest_created_at ? dayjs(stats.latest_created_at).format('MM.DD HH:mm') : '—'}
            </div>
          </Card>
        </Col>
      </Row>

      <div className="opp-toolbar edl-rise edl-rise-3">
        <Space wrap>
          <Select
            value={decision || ''}
            style={{ width: 150 }}
            onChange={(value) => setDecision(value || undefined)}
            options={decisionOptions}
          />
          <Select
            value={status || ''}
            style={{ width: 130 }}
            onChange={(value) => setStatus(value || undefined)}
            options={[
              { value: '', label: '全部状态' },
              ...Object.entries(STATUS_META).map(([key, meta]) => ({
                value: key,
                label: `${meta.label} ${stats?.by_status?.[key] || 0}`,
              })),
            ]}
          />
          <Input.Search
            allowClear
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={() => loadData(1, pageSize)}
            placeholder="项目、采购单位、关键词"
            enterButton={<SearchOutlined />}
            style={{ width: 280 }}
          />
        </Space>
      </div>

      <div className="opp-feed edl-rise edl-rise-4">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading || discovering}
          className="opp-table"
          scroll={{ x: 945 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (nextPage, nextPageSize) => loadData(nextPage, nextPageSize),
          }}
          expandable={{
            expandedRowRender: (record) => (
              <div className="opp-expanded">
                <div className="opp-summary">{record.summary}</div>
                <Row gutter={[18, 12]}>
                  <Col xs={24} md={8}>
                    <div className="opp-section-title">价值判断</div>
                    {(record.why_it_matters || []).map((text) => <p key={text}>{text}</p>)}
                  </Col>
                  <Col xs={24} md={8}>
                    <div className="opp-section-title">主要风险</div>
                    {(record.risks || []).map((text) => <p key={text}>{text}</p>)}
                  </Col>
                  <Col xs={24} md={8}>
                    <div className="opp-section-title">建议动作</div>
                    {(record.recommended_action || []).map((text) => <p key={text}>{text}</p>)}
                  </Col>
                </Row>
              </div>
            ),
          }}
          locale={{ emptyText: <Empty description="暂无标讯线索" /> }}
        />
      </div>
    </div>
  );
};

export default OpportunityRadar;
