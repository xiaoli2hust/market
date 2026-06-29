import React from 'react';
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Upload,
} from 'antd';
import {
  AuditOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  SaveOutlined,
  SendOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import {
  BotActionApproval,
  BotAuditLog,
  BotBroadcastItem,
  BotBroadcastStatus,
  BotChannelAdapter,
  BotChannelBinding,
  BotChatTestResult,
  BotCollaborationRun,
  BotCompliancePolicy,
  BotEnvironment,
  BotEvaluationRun,
  BotEvidenceRecord,
  BotFeedback,
  BotHandoff,
  BotInboxItem,
  BotIntentCorrection,
  BotKnowledgeFile,
  BotKnowledgeSyncJob,
  BotMessage,
  BotProfile,
  BotReleaseVersion,
  BotSkill,
  BotSkillRun,
  BotTask,
  BotTaskRun,
  BotTestCase,
} from '@/services/api';
import { WorkbenchSection } from '@/components/workbench';
import {
  AdapterFormValues,
  ApprovalFormValues,
  BroadcastFormValues,
  ChannelFormValues,
  CollaborationFormValues,
  ComplianceFormValues,
  CorrectionFormValues,
  DEFAULT_BROADCAST_FORM,
  DEFAULT_KNOWLEDGE_FORM,
  EvidenceList,
  FeedbackFormValues,
  HandoffFormValues,
  InboundFormValues,
  KNOWLEDGE_CATEGORIES,
  KnowledgeFormValues,
  KnowledgeSyncFormValues,
  MESSAGE_TYPE_OPTIONS,
  NOTICE_TYPE_OPTIONS,
  ProfileFormValues,
  ReleaseFormValues,
  STATUS_META,
  TaskFormValues,
  TestCaseFormValues,
  formatTime,
} from './botCenterShared';

type BotOption = { value: string; label: React.ReactNode };

type BotCenterViewContext = {
  [key: string]: any;
  currentUser?: { name?: string | null } | null;
  profiles: BotProfile[];
  skills: BotSkill[];
  profileOptions: BotOption[];
  skillOptions: BotOption[];
  bindingOptions: BotOption[];
  selectedProfileData?: BotProfile | null;
  chatMessages: BotMessage[];
  chatResult?: BotChatTestResult | null;
  inboundResult?: BotChatTestResult | null;
  knowledgeFiles: BotKnowledgeFile[];
  syncJobs: BotKnowledgeSyncJob[];
  adapters: BotChannelAdapter[];
  bindings: BotChannelBinding[];
  inboxItems: BotInboxItem[];
  handoffs: BotHandoff[];
  tasks: BotTask[];
  taskRuns: BotTaskRun[];
  approvals: BotActionApproval[];
  testCases: BotTestCase[];
  evaluationRuns: BotEvaluationRun[];
  intentCorrections: BotIntentCorrection[];
  collaborations: BotCollaborationRun[];
  releases: BotReleaseVersion[];
  feedbackItems: BotFeedback[];
  environments: BotEnvironment[];
  compliancePolicies: BotCompliancePolicy[];
  broadcasts: BotBroadcastItem[];
  skillRuns: BotSkillRun[];
  auditLogs: BotAuditLog[];
};

export function renderChannelsTab(ctx: BotCenterViewContext) {
  const {
    loading,
    chatSending,
    selectedProfile,
    profileOptions,
    setSelectedProfile,
    profiles,
    setSimulatedRole,
    handleNewConversation,
    simulatedRole,
    chatMessages,
    selectedProfileData,
    chatInput,
    setChatInput,
    handleChatSend,
    chatResult,
    canConfigure,
    profileForm,
    skillOptions,
    handleSaveProfile,
    skills,
    handleToggleSkill,
    canManageKnowledge,
    knowledgeForm,
    knowledgeFile,
    setKnowledgeFile,
    knowledgeUploading,
    handleCreateKnowledge,
    handleUploadKnowledge,
    knowledgeQuery,
    setKnowledgeQuery,
    handleSearchKnowledge,
    knowledgeSearchResult,
    syncForm,
    handleCreateSyncJob,
    syncJobs,
    syncRunningId,
    handleRunSyncJob,
    knowledgeTotal,
    knowledgeFiles,
    handleUpdateKnowledgeStatus,
    adapterForm,
    adapters,
    handleSaveAdapter,
    channelForm,
    bindings,
    handleSaveChannelBinding,
    inboundForm,
    bindingOptions,
    handleInboundTest,
    inboundResult,
    inboxItems,
    handleUpdateInboxStatus,
    handoffForm,
    handleCreateHandoff,
    handoffs,
    handoffTotal,
    inboxTotal,
    taskForm,
    tasks,
    taskTotal,
    taskRunningId,
    handleCreateTask,
    handleRunTask,
    taskRuns,
    approvalForm,
    approvals,
    approvalTotal,
    handleCreateApproval,
    handleDecideApproval,
    canApprove,
    releaseForm,
    releases,
    releaseTotal,
    publishingVersionId,
    rollingBackVersionId,
    handleCreateRelease,
    handlePublishRelease,
    handleRollbackRelease,
    environments,
    observability,
    feedbackForm,
    feedbackItems,
    feedbackTotal,
    handleCreateFeedback,
    conversationId,
    canEvaluate,
    testCaseForm,
    testCases,
    caseRunningId,
    handleCreateTestCase,
    handleRunCase,
    evaluationRuns,
    intentCorrections,
    correctionForm,
    handleCreateCorrection,
    qualitySummary,
    collaborationForm,
    collaborations,
    collaborationRunning,
    handleRunCollaboration,
    complianceForm,
    compliancePolicies,
    handleSaveCompliancePolicy,
    broadcastForm,
    broadcastSaving,
    handleSaveDraft,
    broadcastSending,
    handleSendNow,
    broadcastStatusFilter,
    setBroadcastStatusFilter,
    loadBroadcasts,
    broadcasts,
    resendingId,
    handleResend,
    canBroadcast,
    currentUser,
    auditLogs,
    skillRuns,
  } = ctx;

  return (
    <div className="bot-channel-grid">
      <WorkbenchSection title="渠道适配器" description="维护各类群聊入口的认证、签名、限流、重试和能力声明。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看渠道策略。" />}
        <Form<AdapterFormValues> form={adapterForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="适配器标识" name="adapter_key">
              <Input placeholder="不填则自动生成；已有标识会更新策略" />
            </Form.Item>
            <Form.Item label="适配器名称" name="name" rules={[{ required: true, message: '请输入适配器名称' }]}>
              <Input placeholder="例如：钉钉群聊机器人" />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="渠道类型" name="channel_type" rules={[{ required: true, message: '请选择渠道类型' }]}>
              <Select options={[
                { value: 'dingtalk', label: '钉钉' },
                { value: 'feishu', label: '飞书' },
                { value: 'wecom', label: '企业微信' },
                { value: 'slack', label: 'Slack' },
                { value: 'teams', label: 'Teams' },
                { value: 'webhook', label: 'Webhook' },
              ]} />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select options={[{ value: 'enabled', label: '启用' }, { value: 'disabled', label: '停用' }]} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="事件模式" name="event_mode">
              <Select options={[{ value: 'webhook', label: 'Webhook 回调' }, { value: 'polling', label: '定时拉取' }, { value: 'stream', label: '长连接事件' }]} />
            </Form.Item>
            <Form.Item label="认证方式" name="auth_scheme">
              <Select options={[
                { value: 'signed_webhook', label: '签名 Webhook' },
                { value: 'oauth2', label: 'OAuth2' },
                { value: 'token', label: 'Token' },
                { value: 'none', label: '无认证' },
              ]} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="每分钟限流" name="rate_limit_per_minute">
              <InputNumber min={1} max={600} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="signing_required" valuePropName="checked">
              <Switch checkedChildren="校验签名" unCheckedChildren="不校验签名" />
            </Form.Item>
          </div>
          <Form.Item label="能力声明" name="capabilities_input">
            <Input placeholder="用逗号分隔，例如：入站消息,群发消息,文件事件" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveAdapter}>保存适配器</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="群聊绑定" description="把钉钉群、内部测试群或其他外部会话绑定到指定机器人。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看群聊绑定。" />}
        <Form<ChannelFormValues> form={channelForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="群聊标识" name="channel_key">
              <Input placeholder="不填则自动生成；已有标识会更新绑定" />
            </Form.Item>
            <Form.Item label="群聊名称" name="channel_name" rules={[{ required: true, message: '请输入群聊名称' }]}>
              <Input placeholder="例如：市场洞察工作群" />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="渠道类型" name="channel_type">
              <Select options={[{ value: 'dingtalk', label: '钉钉' }, { value: 'test_console', label: '测试入口' }, { value: 'webhook', label: 'Webhook' }]} />
            </Form.Item>
            <Form.Item label="绑定机器人" name="bot_profile_key" rules={[{ required: true, message: '请选择机器人' }]}>
              <Select options={profileOptions} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="外部会话 ID" name="external_id">
              <Input placeholder="钉钉 openConversationId，可为空" />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '停用' }]} />
            </Form.Item>
          </div>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveChannelBinding}>保存群聊绑定</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="入站消息测试" description="用真实问法验证群消息路由、Skill 调用和证据链。">
        <Form<InboundFormValues> form={inboundForm} layout="vertical">
          <div className="bot-form-row">
            <Form.Item label="测试群聊" name="channel_key">
              <Select allowClear options={bindingOptions} placeholder="默认使用第一个启用群聊" />
            </Form.Item>
            <Form.Item label="发送人" name="sender_name">
              <Input placeholder={currentUser?.name || '测试用户'} />
            </Form.Item>
          </div>
          <Form.Item label="群聊消息" name="content" rules={[{ required: true, message: '请输入群聊消息' }]}>
            <Input.TextArea rows={4} placeholder="例如：帮我看一下本周公安空间数据相关机会有什么变化" />
          </Form.Item>
          <Button type="primary" icon={<SendOutlined />} onClick={handleInboundTest}>发送入站测试</Button>
        </Form>
        {inboundResult && (
          <div className="bot-preview-answer">
            <strong>机器人回复</strong>
            <p>{inboundResult.assistant_message.content}</p>
            <span>{inboundResult.selected_skills?.length || 0} 个 Skill · {inboundResult.evidence_records?.length || 0} 条证据</span>
          </div>
        )}
      </WorkbenchSection>

      <WorkbenchSection title="人工接管" description="机器人无法闭环或风险较高时，把事项交给负责人处理。">
        {!canApprove && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号没有接管处理权限。" />}
        <Form<HandoffFormValues> form={handoffForm} layout="vertical" disabled={!canApprove}>
          <Form.Item label="收件箱事项" name="inbox_id" rules={[{ required: true, message: '请选择收件箱事项' }]}>
            <Select
              options={inboxItems.map((item) => ({ value: item.inbox_id, label: `${item.priority} · ${item.title}` }))}
              placeholder="选择需要人工接管的事项"
            />
          </Form.Item>
          <div className="bot-form-row">
            <Form.Item label="负责人" name="assignee_name" rules={[{ required: true, message: '请输入负责人' }]}>
              <Input placeholder="例如：张三" />
            </Form.Item>
            <Form.Item label="接管理由" name="reason">
              <Input placeholder="例如：需要销售确认客户状态" />
            </Form.Item>
          </div>
          <Button type="primary" icon={<TeamOutlined />} onClick={handleCreateHandoff}>创建接管</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="适配器列表" description="停用的适配器不会作为入站消息处理策略。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="adapter_key"
          dataSource={adapters}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '适配器', dataIndex: 'name', render: (_: string, record: BotChannelAdapter) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.adapter_key}</span></div> },
            { title: '渠道', dataIndex: 'channel_type', width: 110, render: (value: string) => <Tag color="blue">{value}</Tag> },
            { title: '认证', dataIndex: 'auth_scheme', width: 150 },
            { title: '签名', dataIndex: 'signing_required', width: 90, render: (value: boolean) => value ? <Tag color="success">开启</Tag> : <Tag color="warning">关闭</Tag> },
            { title: '限流', dataIndex: 'rate_limit_per_minute', width: 100, render: (value: number) => `${value}/分钟` },
            { title: '能力', dataIndex: 'capabilities', render: (value: string[]) => (value || []).map((item) => <Tag key={item}>{item}</Tag>) },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'enabled' ? 'success' : 'default'}>{value}</Tag> },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title="绑定列表" description="停用的群聊不会参与真实入站消息路由。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="channel_key"
          dataSource={bindings}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '群聊', dataIndex: 'channel_name' },
            { title: '标识', dataIndex: 'channel_key', width: 180 },
            { title: '类型', dataIndex: 'channel_type', width: 120, render: (value: string) => <Tag color="blue">{value}</Tag> },
            { title: '绑定机器人', dataIndex: 'bot_profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
            { title: '最后消息', dataIndex: 'last_seen_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title={`生产收件箱（${inboxTotal}）`} description="入站消息处理后进入这里，便于追踪未闭环事项。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="inbox_id"
          dataSource={inboxItems}
          pagination={false}
          scroll={{ x: 1180 }}
          columns={[
            { title: '事项', dataIndex: 'title', render: (_: string, record: BotInboxItem) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.inbox_id} · {record.sender_name || '外部用户'}</span></div> },
            { title: '优先级', dataIndex: 'priority', width: 90, render: (value: string) => <Tag color={value === 'P0' ? 'error' : value === 'P1' ? 'warning' : 'default'}>{value}</Tag> },
            { title: '渠道', dataIndex: 'channel_name', width: 160 },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'resolved' ? 'success' : value === 'handoff' ? 'warning' : 'processing'}>{value}</Tag> },
            { title: '负责人', dataIndex: 'owner_name', width: 120, render: (value: string) => value || '—' },
            { title: '最后消息', dataIndex: 'last_message_at', width: 170, render: formatTime },
            {
              title: '操作',
              width: 230,
              render: (_: unknown, record: BotInboxItem) => (
                <Space wrap>
                  <Button size="small" disabled={!canApprove || record.status === 'processing'} onClick={() => handleUpdateInboxStatus(record, 'processing')}>处理中</Button>
                  <Button size="small" disabled={!canApprove || record.status === 'resolved'} onClick={() => handleUpdateInboxStatus(record, 'resolved')}>完成</Button>
                  <Button size="small" disabled={!canApprove} onClick={() => handoffForm.setFieldsValue({ inbox_id: record.inbox_id, assignee_name: currentUser?.name || '' })}>接管</Button>
                </Space>
              ),
            },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title={`接管记录（${handoffTotal}）`} description="人工接管形成单独记录，便于复盘机器人能力边界。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="handoff_id"
          dataSource={handoffs}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '接管编号', dataIndex: 'handoff_id', width: 170 },
            { title: '收件箱', dataIndex: 'inbox_id', width: 170 },
            { title: '负责人', dataIndex: 'assignee_name', width: 130 },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'open' ? 'processing' : 'success'}>{value}</Tag> },
            { title: '理由', dataIndex: 'reason' },
            { title: '申请人', dataIndex: 'requested_by_name', width: 120 },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
