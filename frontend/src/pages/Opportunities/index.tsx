import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  AlertOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CommentOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  LinkOutlined,
  ReloadOutlined,
  RiseOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { history } from '@@/exports';
import {
  ActivityItem,
  fetchActivities,
  fetchOpportunityLeads,
  fetchOpportunityLeadStats,
  OpportunityLead,
  OpportunityLeadStats,
} from '@/services/api';
import './opportunities.less';

const { Title } = Typography;

type WorkbenchMode = 'follow' | 'sign' | 'payment';

const modeFilter: Record<WorkbenchMode, RegExp> = {
  follow: /商机|客户|拜访|方案|POC|项目推进|招投标|合同|回款/,
  sign: /商机|招投标|投标|合同|方案|POC|项目推进/,
  payment: /回款|验收|合同|付款|到账|发票/,
};

const gapItems = [
  {
    title: '商机主数据',
    status: '需契约',
    text: '需要销售侧提供商机编号、客户、负责人、阶段、预计签单与更新时间。',
  },
  {
    title: '销售追问记录',
    status: '需契约',
    text: '需要销售侧提供机器人追问结果；平台只跟进进度，不替销售生成预测。',
  },
  {
    title: '签单预测回传',
    status: '需契约',
    text: '需要销售侧提供已确认的签单预测金额、日期、置信度和变更原因。',
  },
  {
    title: '回款计划与事实',
    status: '需契约',
    text: '需要合同侧提供回款计划、开票、验收和到账事实，避免用页面推测金额。',
  },
];

const formatBudget = (value?: number | null) => {
  if (!value) return '未披露';
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  return `${(value / 10000).toFixed(1)}万`;
};

const isOpportunityActivity = (item: ActivityItem) => {
  const text = [
    item.action_type,
    item.action_type_label,
    item.opportunity_name,
    item.customer_name,
    item.summary,
    item.detail,
  ].join(' ');
  return Boolean(item.opportunity_id || item.opportunity_name || modeFilter.follow.test(text));
};

const Opportunities: React.FC = () => {
  const [mode, setMode] = useState<WorkbenchMode>('follow');
  const [loading, setLoading] = useState(false);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [convertedLeads, setConvertedLeads] = useState<OpportunityLead[]>([]);
  const [leadStats, setLeadStats] = useState<OpportunityLeadStats | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [activityResp, leadsResp, statsResp] = await Promise.all([
        fetchActivities({ page: 1, page_size: 150 }),
        fetchOpportunityLeads({ status: 'converted', page: 1, page_size: 8 }).catch(() => ({ items: [] })),
        fetchOpportunityLeadStats().catch(() => null),
      ]);
      setActivities(activityResp.list || []);
      setConvertedLeads(leadsResp.items || []);
      setLeadStats(statsResp);
    } catch (err: any) {
      message.error(err?.message || '商机数据加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const opportunityActivities = useMemo(
    () => activities.filter(isOpportunityActivity),
    [activities],
  );

  const tableData = useMemo(() => {
    const filter = modeFilter[mode];
    return opportunityActivities
      .filter((item) => filter.test([
        item.action_type,
        item.opportunity_name,
        item.customer_name,
        item.summary,
      ].join(' ')))
      .slice(0, 60);
  }, [mode, opportunityActivities]);

  const riskActivities = useMemo(
    () => opportunityActivities.filter((item) => /风险|延期|延迟|逾期|未确认|待确认|介入|阻塞|回款/.test(item.summary || item.detail || '')).slice(0, 12),
    [opportunityActivities],
  );

  const connectedEvidenceCount = [
    opportunityActivities.length > 0,
    convertedLeads.length > 0,
  ].filter(Boolean).length;

  const columns: ColumnsType<ActivityItem> = [
    {
      title: '商机 / 客户',
      dataIndex: 'opportunity_name',
      render: (_, record) => (
        <div className="opp-name">
          <div className="opp-main">{record.opportunity_name || record.customer_name || '未命名商机'}</div>
          <div className="opp-meta">
            <span>{record.customer_name || '客户未标注'}</span>
            <span>{record.user_name || '负责人未标注'} · {record.user_department || '部门未标注'}</span>
          </div>
        </div>
      ),
    },
    {
      title: '最近动作',
      dataIndex: 'summary',
      render: (_, record) => (
        <div className="opp-question">
          <RobotOutlined />
          <span>
            <Tag>{record.action_type_label || record.action_type || '活动'}</Tag>
            {record.summary || record.detail || '无摘要'}
          </span>
        </div>
      ),
    },
    {
      title: '日期',
      dataIndex: 'activity_date',
      width: 118,
      render: (value: string) => <span className="opp-date edl-mono">{value ? dayjs(value).format('YYYY.MM.DD') : '—'}</span>,
    },
    {
      title: '证据',
      dataIndex: 'source',
      width: 112,
      render: () => <Tag color="blue">日报活动</Tag>,
    },
  ];

  return (
    <div className="opp-center">
      <div className="opp-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">Opportunity Workbench · 商机中心</div>
          <Title className="opp-title" level={1}>
            商机<span className="accent">跟进台</span>
          </Title>
          <div className="opp-sub">已接入日报商机动作与标讯确认线索；签单、回款、销售追问等待销售侧机制接入</div>
        </div>
        <Space wrap>
          <Button icon={<FileSearchOutlined />} onClick={() => history.push('/intelligence/opportunities')}>
            标讯线索确认
          </Button>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      <hr className="edl-rule-strong" />

      <Row className="opp-stats edl-rise edl-rise-2" gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><CheckCircleOutlined /> 已确认线索</div>
            <div className="opp-stat-value"><span className="edl-display">{leadStats?.by_status?.converted || convertedLeads.length}</span><span>条</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><CommentOutlined /> 商机活动</div>
            <div className="opp-stat-value"><span className="edl-display">{opportunityActivities.length}</span><span>条</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><AlertOutlined /> 待关注</div>
            <div className="opp-stat-value"><span className="edl-display">{riskActivities.length}</span><span>项</span></div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="opp-stat-card" variant="borderless">
            <div className="opp-stat-label"><DatabaseOutlined /> 已接入证据源</div>
            <div className="opp-stat-value"><span className="edl-display">{connectedEvidenceCount}</span><span>类</span></div>
          </Card>
        </Col>
      </Row>

      <div className="opp-loop edl-rise edl-rise-2">
        {[
          { icon: <CommentOutlined />, label: '日报活动证据', value: opportunityActivities.length, unit: '条', status: '已接入' },
          { icon: <FileSearchOutlined />, label: '标讯确认线索', value: convertedLeads.length, unit: '条', status: '已接入' },
          { icon: <RobotOutlined />, label: '销售侧商机机制', value: gapItems.length, unit: '项契约待补', status: '需业务确认' },
        ].map((step, index) => (
          <div className="opp-loop-step" key={step.label}>
            <div className="opp-loop-icon">{step.icon}</div>
            <div>
              <div className="opp-loop-label">{step.label}</div>
              <div className="opp-loop-value"><span>{step.value}</span>{step.unit}</div>
              <Tag color={step.status === '已接入' ? 'green' : 'orange'}>{step.status}</Tag>
            </div>
            {index < 2 && <ArrowRightOutlined className="opp-loop-arrow" />}
          </div>
        ))}
      </div>

      <Row className="opp-work edl-rise edl-rise-3" gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <div className="opp-panel">
            <div className="opp-panel-head">
              <div>
                <div className="edl-eyebrow">Confirmed Leads</div>
                <h3>已确认标讯线索</h3>
              </div>
              <Button size="small" type="link" onClick={() => history.push('/intelligence/opportunities')}>
                查看线索 <ArrowRightOutlined />
              </Button>
            </div>
            <div className="opp-intake-list">
              {convertedLeads.length === 0 ? (
                <Empty description="暂无已确认线索" />
              ) : convertedLeads.map((lead) => (
                <div className="opp-intake" key={lead.id}>
                  <div>
                    <div className="opp-intake-title">{lead.project_name}</div>
                    <div className="opp-intake-meta">
                      <Tag color={lead.score >= 80 ? 'red' : 'orange'}>评分 {lead.score}</Tag>
                      <span>{lead.buyer || '采购单位未披露'}</span>
                      <span>{formatBudget(lead.budget)}</span>
                    </div>
                  </div>
                  <Button size="small" icon={<LinkOutlined />} onClick={() => window.open(lead.url, '_blank', 'noopener,noreferrer')}>
                    原文
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </Col>
        <Col xs={24} lg={14}>
          <div className="opp-panel">
            <div className="opp-panel-head">
              <div>
                <div className="edl-eyebrow">Readiness</div>
                <h3>销售机制接入状态</h3>
              </div>
              <Tag color="orange">缺少销售侧契约</Tag>
            </div>
            <div className="opp-gap-list">
              {gapItems.map((item) => (
                <div className="opp-gap" key={item.title}>
                  <Tag color="orange">{item.status}</Tag>
                  <strong>{item.title}</strong>
                  <span>{item.text}</span>
                </div>
              ))}
            </div>
          </div>
        </Col>
      </Row>

      <div className="opp-feed edl-rise edl-rise-4">
        <div className="opp-feed-head">
          <div>
            <div className="edl-eyebrow">Evidence Feed</div>
            <h3>已接入的商机跟进证据</h3>
          </div>
          <Segmented
            value={mode}
            onChange={(value) => setMode(value as WorkbenchMode)}
            options={[
              { value: 'follow', label: '跟进活动', icon: <RobotOutlined /> },
              { value: 'sign', label: '签单相关', icon: <RiseOutlined /> },
              { value: 'payment', label: '回款相关', icon: <CheckCircleOutlined /> },
            ]}
          />
        </div>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={tableData}
          loading={loading}
          pagination={{ pageSize: 10 }}
          className="opp-table"
          locale={{ emptyText: <Empty description="暂无已接入商机证据" /> }}
        />
        <div className="opp-foot-note">
          <ClockCircleOutlined /> 当前页面只展示已有证据，不生成预测金额。
        </div>
      </div>
    </div>
  );
};

export default Opportunities;
