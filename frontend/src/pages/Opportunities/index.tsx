import React, { useState } from 'react';
import {
  Card,
  Col,
  Empty,
  Row,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import {
  DollarOutlined,
  RiseOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import './opportunities.less';

const { Title } = Typography;

// ---------- Mock 数据 ----------

interface OpportunityForecast {
  id: number;
  opportunity_name: string;
  customer_name: string;
  owner_name: string;
  department: string;
  forecast_amount: number;
  forecast_date: string;
  stage: string;
  confidence: number;
  last_confirmed_at: string;
  notes: string;
}

const MOCK_SIGN_DATA: OpportunityForecast[] = [
  {
    id: 1,
    opportunity_name: '智慧警务地理信息平台三期',
    customer_name: '北京市公安局',
    owner_name: '张伟',
    department: '华北组',
    forecast_amount: 580,
    forecast_date: '2026-07-15',
    stage: '方案评审',
    confidence: 0.85,
    last_confirmed_at: '2026-06-10',
    notes: '已完成技术方案评审，等待客户内部立项审批',
  },
  {
    id: 2,
    opportunity_name: '城市运行管理大数据平台',
    customer_name: '上海市住建委',
    owner_name: '李明',
    department: '华东组',
    forecast_amount: 420,
    forecast_date: '2026-08-01',
    stage: '招投标',
    confidence: 0.7,
    last_confirmed_at: '2026-06-08',
    notes: '已购买标书，正在准备投标材料',
  },
  {
    id: 3,
    opportunity_name: '数字孪生水务系统',
    customer_name: '深圳水务集团',
    owner_name: '王芳',
    department: '行业组',
    forecast_amount: 350,
    forecast_date: '2026-06-30',
    stage: '合同谈判',
    confidence: 0.9,
    last_confirmed_at: '2026-06-12',
    notes: '合同条款基本达成一致，本周内预计签约',
  },
  {
    id: 4,
    opportunity_name: '智慧交通数据中台',
    customer_name: '广州市交研院',
    owner_name: '陈杰',
    department: '行业组',
    forecast_amount: 280,
    forecast_date: '2026-09-15',
    stage: '需求确认',
    confidence: 0.5,
    last_confirmed_at: '2026-06-05',
    notes: '初步接触，客户有预算但需求尚不明确',
  },
  {
    id: 5,
    opportunity_name: '政务大数据治理平台',
    customer_name: '成都市政数局',
    owner_name: '赵强',
    department: '华北组',
    forecast_amount: 650,
    forecast_date: '2026-07-30',
    stage: 'POC验证',
    confidence: 0.75,
    last_confirmed_at: '2026-06-11',
    notes: 'POC环境已部署完成，下周进行演示汇报',
  },
];

const MOCK_PAYMENT_DATA: OpportunityForecast[] = [
  {
    id: 101,
    opportunity_name: '智慧城市一期（尾款）',
    customer_name: '杭州市城管局',
    owner_name: '张伟',
    department: '华北组',
    forecast_amount: 180,
    forecast_date: '2026-06-25',
    stage: '验收完成',
    confidence: 0.95,
    last_confirmed_at: '2026-06-12',
    notes: '验收报告已签署，等待财务走付款流程',
  },
  {
    id: 102,
    opportunity_name: '数据治理平台（首付款）',
    customer_name: '南京市信息中心',
    owner_name: '李明',
    department: '华东组',
    forecast_amount: 120,
    forecast_date: '2026-06-20',
    stage: '已签约',
    confidence: 0.9,
    last_confirmed_at: '2026-06-09',
    notes: '合同已签署，首付款发票已开具',
  },
  {
    id: 103,
    opportunity_name: '交通大数据项目（阶段款）',
    customer_name: '武汉交通委',
    owner_name: '王芳',
    department: '行业组',
    forecast_amount: 240,
    forecast_date: '2026-07-10',
    stage: '项目交付',
    confidence: 0.8,
    last_confirmed_at: '2026-06-07',
    notes: '第二阶段交付物已提交，等待验收确认',
  },
  {
    id: 104,
    opportunity_name: '应急指挥平台（终验款）',
    customer_name: '重庆市应急局',
    owner_name: '陈杰',
    department: '行业组',
    forecast_amount: 95,
    forecast_date: '2026-08-15',
    stage: '终验中',
    confidence: 0.6,
    last_confirmed_at: '2026-06-06',
    notes: '终验进行中，客户反馈需要补充部分材料',
  },
];

// ---------- 组件 ----------

const STAGE_COLORS: Record<string, string> = {
  需求确认: 'default',
  方案评审: 'processing',
  招投标: 'blue',
  POC验证: 'cyan',
  合同谈判: 'orange',
  已签约: 'green',
  项目交付: 'purple',
  验收完成: 'green',
  终验中: 'orange',
};

const Opportunities: React.FC = () => {
  const [tab, setTab] = useState<string>('sign');

  const currentData = tab === 'sign' ? MOCK_SIGN_DATA : MOCK_PAYMENT_DATA;

  // 汇总计算
  const totalAmount = currentData.reduce((sum, d) => sum + d.forecast_amount, 0);
  const thisMonthAmount = currentData
    .filter((d) => dayjs(d.forecast_date).month() === dayjs().month())
    .reduce((sum, d) => sum + d.forecast_amount, 0);
  const avgConfidence =
    currentData.length > 0
      ? currentData.reduce((sum, d) => sum + d.confidence, 0) / currentData.length
      : 0;
  const highConfidenceCount = currentData.filter((d) => d.confidence >= 0.8).length;

  const columns = [
    {
      title: tab === 'sign' ? '商机名称' : '项目/款项',
      dataIndex: 'opportunity_name',
      ellipsis: true,
      render: (text: string) => (
        <span style={{ fontFamily: 'var(--serif)', fontWeight: 600 }}>{text}</span>
      ),
    },
    {
      title: '客户',
      dataIndex: 'customer_name',
      width: 150,
    },
    {
      title: '负责人',
      dataIndex: 'owner_name',
      width: 90,
      render: (name: string, record: OpportunityForecast) => (
        <span>
          {name}
          <span style={{ fontSize: 11, color: 'var(--ink-faint)', marginLeft: 4 }}>
            {record.department}
          </span>
        </span>
      ),
    },
    {
      title: tab === 'sign' ? '预测签单额' : '预测回款额',
      dataIndex: 'forecast_amount',
      width: 120,
      sorter: (a: OpportunityForecast, b: OpportunityForecast) => a.forecast_amount - b.forecast_amount,
      render: (amount: number) => (
        <span className="opp-amount edl-mono">
          {amount}<span className="opp-amount-unit">万</span>
        </span>
      ),
    },
    {
      title: tab === 'sign' ? '预计签单日期' : '预计回款日期',
      dataIndex: 'forecast_date',
      width: 120,
      sorter: (a: OpportunityForecast, b: OpportunityForecast) =>
        dayjs(a.forecast_date).valueOf() - dayjs(b.forecast_date).valueOf(),
      render: (date: string) => (
        <span className="edl-mono" style={{ fontSize: 12 }}>
          {dayjs(date).format('YYYY·MM·DD')}
        </span>
      ),
    },
    {
      title: '阶段',
      dataIndex: 'stage',
      width: 100,
      render: (stage: string) => (
        <Tag color={STAGE_COLORS[stage] || 'default'} style={{ margin: 0 }}>
          {stage}
        </Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 80,
      sorter: (a: OpportunityForecast, b: OpportunityForecast) => a.confidence - b.confidence,
      render: (val: number) => (
        <span
          style={{
            fontFamily: 'var(--mono)',
            color: val >= 0.8 ? '#52c41a' : val >= 0.6 ? '#faad14' : '#ff4d4f',
            fontWeight: 600,
          }}
        >
          {Math.round(val * 100)}%
        </span>
      ),
    },
    {
      title: '备注',
      dataIndex: 'notes',
      ellipsis: true,
      render: (text: string) => (
        <span style={{ fontSize: 12, color: 'var(--ink-faint)' }}>{text || '—'}</span>
      ),
    },
    {
      title: '最近确认',
      dataIndex: 'last_confirmed_at',
      width: 100,
      render: (date: string) => (
        <span className="edl-mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>
          {dayjs(date).format('MM·DD')}
        </span>
      ),
    },
  ];

  return (
    <div className="opp">
      {/* Headline */}
      <div className="opp-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">Business Pipeline · 商机管线</div>
          <Title className="opp-title" level={1}>
            商机<span className="accent">数据</span>
          </Title>
          <div className="opp-sub">
            签单预测 · 回款预测 · 进展追踪
            <span className="edl-mono"> · 机器人定期与销售确认更新</span>
          </div>
        </div>
      </div>

      <hr className="edl-rule-strong" />

      {/* Summary stats */}
      <div className="opp-stats edl-rise edl-rise-2">
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <Card className="opp-stat-card" bordered={false}>
              <div className="opp-stat-label">
                <DollarOutlined /> {tab === 'sign' ? '预测签单总额' : '预测回款总额'}
              </div>
              <div className="opp-stat-value">
                <span className="edl-display">{totalAmount}</span>
                <span className="opp-stat-unit">万元</span>
              </div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="opp-stat-card" bordered={false}>
              <div className="opp-stat-label">
                <ClockCircleOutlined /> 本月预期
              </div>
              <div className="opp-stat-value">
                <span className="edl-display">{thisMonthAmount}</span>
                <span className="opp-stat-unit">万元</span>
              </div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="opp-stat-card" bordered={false}>
              <div className="opp-stat-label">
                <RiseOutlined /> 平均置信度
              </div>
              <div className="opp-stat-value">
                <span className="edl-display" style={{ color: avgConfidence >= 0.8 ? '#52c41a' : '#faad14' }}>
                  {Math.round(avgConfidence * 100)}
                </span>
                <span className="opp-stat-unit">%</span>
              </div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="opp-stat-card" bordered={false}>
              <div className="opp-stat-label">
                <CheckCircleOutlined /> 高置信商机
              </div>
              <div className="opp-stat-value">
                <span className="edl-display">{highConfidenceCount}</span>
                <span className="opp-stat-unit">个</span>
              </div>
            </Card>
          </Col>
        </Row>
      </div>

      {/* Tabs */}
      <div className="opp-feed edl-rise edl-rise-3">
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: 'sign',
              label: (
                <span>
                  <DollarOutlined /> 签单预测
                  <Tag color="blue" style={{ marginLeft: 6, fontSize: 10 }}>
                    {MOCK_SIGN_DATA.length}
                  </Tag>
                </span>
              ),
            },
            {
              key: 'payment',
              label: (
                <span>
                  <CheckCircleOutlined /> 回款预测
                  <Tag color="green" style={{ marginLeft: 6, fontSize: 10 }}>
                    {MOCK_PAYMENT_DATA.length}
                  </Tag>
                </span>
              ),
            },
          ]}
        />

        <Table
          rowKey="id"
          columns={columns}
          dataSource={currentData}
          size="middle"
          className="opp-table"
          pagination={false}
          locale={{ emptyText: <Empty description="暂无预测数据" /> }}
        />

        <div className="opp-foot-note">
          <span className="edl-eyebrow">
            数据来源：钉钉机器人定期与销售确认 · 最近一次更新 {dayjs().format('YYYY·MM·DD')}
          </span>
        </div>
      </div>
    </div>
  );
};

export default Opportunities;
