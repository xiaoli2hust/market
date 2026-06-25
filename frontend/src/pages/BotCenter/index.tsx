import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { history } from '@@/exports';
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  message,
} from 'antd';
import {
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FieldTimeOutlined,
  RobotOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  BotBroadcastItem,
  BotBroadcastPayload,
  BotBroadcastStatus,
  BotMessageType,
  createBotBroadcast,
  fetchBotBroadcasts,
  getApiErrorMessage,
  getCurrentUser,
  sendBotBroadcast,
  sendExistingBotBroadcast,
  userHasPermission,
} from '@/services/api';
import {
  WorkbenchMetricGrid,
  WorkbenchPageHeader,
  WorkbenchSection,
  WorkbenchStatusRail,
} from '@/components/workbench';
import './bot-center.less';

const PAGE_SIZE = 10;

const STATUS_META: Record<BotBroadcastStatus, { label: string; color: string; icon: React.ReactNode }> = {
  draft: { label: '草稿', color: 'default', icon: <ClockCircleOutlined /> },
  sending: { label: '发送中', color: 'processing', icon: <FieldTimeOutlined /> },
  sent: { label: '已发送', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '发送失败', color: 'error', icon: <ExclamationCircleOutlined /> },
};

const NOTICE_TYPE_OPTIONS = [
  { value: 'general', label: '普通通知' },
  { value: 'daily_report', label: '日报周报' },
  { value: 'market_digest', label: '市场速递' },
  { value: 'bidding_alert', label: '标讯提醒' },
  { value: 'task_followup', label: '任务提醒' },
];

const MESSAGE_TYPE_OPTIONS: Array<{ value: BotMessageType; label: string }> = [
  { value: 'markdown', label: '图文排版' },
  { value: 'text', label: '纯文本' },
];

type BroadcastFormValues = BotBroadcastPayload & {
  notice_type?: string;
};

const BotCenter: React.FC = () => {
  const currentUser = getCurrentUser();
  const canBroadcast = userHasPermission(currentUser, 'bot:broadcast');
  const [form] = Form.useForm<BroadcastFormValues>();
  const [broadcasts, setBroadcasts] = useState<BotBroadcastItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<BotBroadcastStatus | 'all'>('all');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [resendingId, setResendingId] = useState<number | null>(null);

  const loadBroadcasts = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetchBotBroadcasts({
        page,
        page_size: PAGE_SIZE,
        status: statusFilter === 'all' ? undefined : statusFilter,
      });
      setBroadcasts(resp?.items || []);
      setTotal(resp?.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载群发记录失败'));
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    form.setFieldsValue({
      message_type: 'markdown',
      notice_type: 'general',
      target_type: 'configured_group',
      at_all: false,
    });
  }, [form]);

  useEffect(() => {
    loadBroadcasts();
  }, [loadBroadcasts]);

  const currentPageStats = useMemo(() => {
    const sent = broadcasts.filter((item) => item.status === 'sent').length;
    const failed = broadcasts.filter((item) => item.status === 'failed').length;
    const draft = broadcasts.filter((item) => item.status === 'draft').length;
    return { sent, failed, draft };
  }, [broadcasts]);

  const buildPayload = async (): Promise<BotBroadcastPayload> => {
    const values = await form.validateFields();
    return {
      title: values.title.trim(),
      content: values.content.trim(),
      message_type: values.message_type || 'markdown',
      target_type: 'configured_group',
      at_all: Boolean(values.at_all),
      target_payload: {
        notice_type: values.notice_type || 'general',
        requested_by: currentUser?.name || currentUser?.role || '系统用户',
      },
    };
  };

  const handleSaveDraft = async () => {
    if (!canBroadcast) return;
    setSaving(true);
    try {
      const payload = await buildPayload();
      await createBotBroadcast(payload);
      message.success('草稿已保存');
      form.resetFields();
      form.setFieldsValue({ message_type: 'markdown', notice_type: 'general', target_type: 'configured_group', at_all: false });
      const resp = await fetchBotBroadcasts({ page: 1, page_size: PAGE_SIZE });
      setBroadcasts(resp?.items || []);
      setTotal(resp?.total || 0);
      setStatusFilter('all');
      setPage(1);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存草稿失败'));
    } finally {
      setSaving(false);
    }
  };

  const handleSendNow = async () => {
    if (!canBroadcast) return;
    setSending(true);
    try {
      const payload = await buildPayload();
      const result = await sendBotBroadcast(payload);
      if (result.status === 'sent') {
        message.success('消息已发送到钉钉群');
      } else {
        message.error(result.error_message || result.result_message || '消息发送失败');
      }
      form.resetFields();
      form.setFieldsValue({ message_type: 'markdown', notice_type: 'general', target_type: 'configured_group', at_all: false });
      const resp = await fetchBotBroadcasts({ page: 1, page_size: PAGE_SIZE });
      setBroadcasts(resp?.items || []);
      setTotal(resp?.total || 0);
      setStatusFilter('all');
      setPage(1);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '发送失败'));
    } finally {
      setSending(false);
    }
  };

  const handleResend = async (record: BotBroadcastItem) => {
    if (!canBroadcast) return;
    setResendingId(record.id);
    try {
      const result = await sendExistingBotBroadcast(record.id);
      if (result.status === 'sent') {
        message.success('消息已重新发送');
      } else {
        message.error(result.error_message || result.result_message || '重新发送失败');
      }
      await loadBroadcasts();
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '重新发送失败'));
    } finally {
      setResendingId(null);
    }
  };

  const columns = [
    {
      title: '消息',
      dataIndex: 'title',
      width: 300,
      render: (_: string, record: BotBroadcastItem) => (
        <div className="bot-table-title">
          <strong>{record.title}</strong>
          <span>{record.content}</span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: BotBroadcastStatus) => {
        const meta = STATUS_META[value] || STATUS_META.draft;
        return <Tag icon={meta.icon} color={meta.color}>{meta.label}</Tag>;
      },
    },
    {
      title: '收件范围',
      dataIndex: 'target_summary',
      width: 190,
      render: (value: string, record: BotBroadcastItem) => (
        <Space direction="vertical" size={2}>
          <span>{value || '当前钉钉默认群'}</span>
          {record.at_all && <Tag color="volcano">提醒所有人</Tag>}
        </Space>
      ),
    },
    {
      title: '创建/发送',
      width: 210,
      render: (_: unknown, record: BotBroadcastItem) => (
        <div className="bot-time-cell">
          <span>创建：{formatTime(record.created_at)}</span>
          <span>发送：{formatTime(record.sent_at)}</span>
        </div>
      ),
    },
    {
      title: '结果',
      dataIndex: 'result_message',
      render: (value: string, record: BotBroadcastItem) => (
        <Tooltip title={record.error_message || value || '暂无发送结果'}>
          <span className={record.status === 'failed' ? 'bot-result is-error' : 'bot-result'}>
            {record.error_message || value || '—'}
          </span>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      width: 112,
      render: (_: unknown, record: BotBroadcastItem) => {
        const canResend = canBroadcast && ['draft', 'failed'].includes(record.status);
        if (!canResend) return <span className="bot-muted">无可用操作</span>;
        return (
          <Popconfirm
            title="确认发送这条消息？"
            description="消息会发送到当前钉钉默认群。"
            okText="发送"
            cancelText="取消"
            onConfirm={() => handleResend(record)}
          >
            <Button
              size="small"
              icon={<SendOutlined />}
              loading={resendingId === record.id}
            >
              发送
            </Button>
          </Popconfirm>
        );
      },
    },
  ];

  return (
    <div className="bot-center">
      <WorkbenchPageHeader
        eyebrow="AGENT ACTION"
        title="机器人中心"
        accent="群发"
        description="统一承接面向群聊的机器人动作：人工通知、日报周报推送、市场速递提醒和后续自动任务。"
        actions={[
          {
            label: '钉钉配置',
            icon: <SettingOutlined />,
            onClick: () => history.push('/management'),
          },
        ]}
      />

      <WorkbenchStatusRail
        items={[
          {
            label: '默认收件群',
            value: '钉钉默认群',
            status: 'good',
            meta: '由管理中心的机器人配置决定',
          },
          {
            label: '当前权限',
            value: canBroadcast ? '可群发' : '只读',
            status: canBroadcast ? 'good' : 'warn',
            meta: canBroadcast ? '发送动作会写入审计记录' : '需要管理员授予群发权限',
          },
          {
            label: '记录总数',
            value: `${total} 条`,
            status: 'muted',
            meta: '草稿、成功、失败均可追踪',
          },
        ]}
      />

      <WorkbenchMetricGrid
        metrics={[
          { label: '本页已发送', value: currentPageStats.sent, icon: <CheckCircleOutlined />, tone: 'green', hint: '钉钉接口返回成功的消息' },
          { label: '本页草稿', value: currentPageStats.draft, icon: <ClockCircleOutlined />, tone: 'gold', hint: '可确认后发送' },
          { label: '本页失败', value: currentPageStats.failed, icon: <ExclamationCircleOutlined />, tone: 'red', hint: '可查看原因并重试' },
          { label: '消息上限', value: '5000', suffix: '字', icon: <BellOutlined />, tone: 'neutral', hint: '避免群消息过长影响阅读' },
        ]}
      />

      <WorkbenchSection
        title="消息群发"
        description="第一版只支持发送到当前钉钉默认群；后续可扩展部门群、项目群和临时人群。"
      >
        {!canBroadcast && (
          <Alert
            className="bot-permission-alert"
            type="warning"
            showIcon
            message="当前账号没有群发权限"
            description="你可以查看发送记录，但不能创建草稿或发送消息。"
          />
        )}
        <div className="bot-broadcast-grid">
          <Form<BroadcastFormValues>
            form={form}
            layout="vertical"
            className="bot-broadcast-form"
            disabled={!canBroadcast}
          >
            <div className="bot-form-row">
              <Form.Item
                label="消息标题"
                name="title"
                rules={[
                  { required: true, message: '请输入消息标题' },
                  { max: 120, message: '标题不能超过120字' },
                ]}
              >
                <Input placeholder="例如：本周市场洞察重点提醒" maxLength={120} showCount />
              </Form.Item>
              <Form.Item label="消息类型" name="message_type">
                <Select options={MESSAGE_TYPE_OPTIONS} />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="通知类别" name="notice_type">
                <Select options={NOTICE_TYPE_OPTIONS} />
              </Form.Item>
              <Form.Item label="发送范围" name="target_type">
                <Select
                  disabled
                  options={[{ value: 'configured_group', label: '当前钉钉默认群' }]}
                />
              </Form.Item>
            </div>
            <Form.Item
              label="消息正文"
              name="content"
              rules={[
                { required: true, message: '请输入消息正文' },
                { max: 5000, message: '正文不能超过5000字' },
              ]}
            >
              <Input.TextArea
                rows={9}
                maxLength={5000}
                showCount
                placeholder="输入要发送给群内成员的内容。图文排版模式支持 Markdown。"
              />
            </Form.Item>
            <div className="bot-form-actions">
              <Form.Item name="at_all" valuePropName="checked" noStyle>
                <Switch checkedChildren="@所有人" unCheckedChildren="普通发送" />
              </Form.Item>
              <Space wrap>
                <Button
                  icon={<SaveOutlined />}
                  loading={saving}
                  onClick={handleSaveDraft}
                >
                  保存草稿
                </Button>
                <Popconfirm
                  title="确认立即群发？"
                  description="消息会发送到当前钉钉默认群，发送结果会写入记录。"
                  okText="确认发送"
                  cancelText="再检查"
                  onConfirm={handleSendNow}
                >
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    loading={sending}
                  >
                    确认发送
                  </Button>
                </Popconfirm>
              </Space>
            </div>
          </Form>

          <div className="bot-policy-panel">
            <div className="bot-policy-icon"><TeamOutlined /></div>
            <h3>群发规则</h3>
            <ul>
              <li>消息默认发往管理中心配置的钉钉机器人群。</li>
              <li>发送、失败、重试都会保存记录，方便追溯。</li>
              <li>没有钉钉配置时，发送会失败并展示原因，不会静默吞掉。</li>
              <li>涉及经营数字或标讯结论时，建议附上来源链接或证据摘要。</li>
            </ul>
          </div>
        </div>
      </WorkbenchSection>

      <WorkbenchSection
        title="发送记录"
        description="这里不是展示样例，记录来自后端群发表。失败草稿可以重新发送。"
        action={
          <Space wrap>
            <Select
              value={statusFilter}
              style={{ width: 132 }}
              onChange={(value) => {
                setStatusFilter(value);
                setPage(1);
              }}
              options={[
                { value: 'all', label: '全部状态' },
                { value: 'draft', label: '草稿' },
                { value: 'sent', label: '已发送' },
                { value: 'failed', label: '发送失败' },
              ]}
            />
            <Button onClick={loadBroadcasts}>刷新</Button>
          </Space>
        }
      >
        <Spin spinning={loading}>
          <Table
            className="edl-table bot-record-table"
            rowKey="id"
            columns={columns}
            dataSource={broadcasts}
            locale={{ emptyText: <Empty description="暂无群发记录" /> }}
            pagination={{
              current: page,
              pageSize: PAGE_SIZE,
              total,
              showSizeChanger: false,
              onChange: setPage,
            }}
            scroll={{ x: 980 }}
          />
        </Spin>
      </WorkbenchSection>

      <WorkbenchSection
        title="自动任务入口"
        description="群发中心负责消息与审计；定时规则仍在管理中心维护，避免把配置分散到多个地方。"
      >
        <div className="bot-task-grid">
          <TaskCard
            icon={<RobotOutlined />}
            title="日报周报推送"
            text="由日报周报模块生成报告，再通过机器人推送查看链接。"
            action="查看日报周报"
            onClick={() => history.push('/dashboard')}
          />
          <TaskCard
            icon={<BellOutlined />}
            title="市场速递提醒"
            text="由市场洞察采集与分析后生成速递，再触发钉钉推送。"
            action="查看市场洞察"
            onClick={() => history.push('/intelligence')}
          />
          <TaskCard
            icon={<SettingOutlined />}
            title="任务调度配置"
            text="采集频率、机器人参数、接口密钥统一放在管理中心。"
            action="打开管理中心"
            onClick={() => history.push('/management')}
          />
        </div>
      </WorkbenchSection>
    </div>
  );
};

const TaskCard: React.FC<{
  icon: React.ReactNode;
  title: string;
  text: string;
  action: string;
  onClick: () => void;
}> = ({ icon, title, text, action, onClick }) => (
  <div className="bot-task-card">
    <i>{icon}</i>
    <div>
      <h3>{title}</h3>
      <p>{text}</p>
      <Button size="small" onClick={onClick}>{action}</Button>
    </div>
  </div>
);

function formatTime(value?: string | null): string {
  if (!value) return '—';
  return dayjs(value).format('YYYY-MM-DD HH:mm');
}

export default BotCenter;
