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

export function renderBroadcastTab(ctx: BotCenterViewContext) {
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
    <div className="bot-broadcast-tab">
      <WorkbenchSection title="消息群发" description="群发是受控动作；测试对话只生成待确认草稿，不直接发送外部消息。">
        {!canBroadcast && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号没有群发权限" />}
        <Form<BroadcastFormValues>
          form={broadcastForm}
          layout="vertical"
          disabled={!canBroadcast}
          initialValues={DEFAULT_BROADCAST_FORM}
        >
          <div className="bot-form-row">
            <Form.Item label="消息标题" name="title" rules={[{ required: true, message: '请输入消息标题' }, { max: 120, message: '标题不能超过120字' }]}>
              <Input data-testid="bot-broadcast-title" placeholder="例如：本周市场洞察重点提醒" maxLength={120} showCount />
            </Form.Item>
            <Form.Item label="消息类型" name="message_type">
              <Select options={MESSAGE_TYPE_OPTIONS} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="通知类别" name="notice_type"><Select options={NOTICE_TYPE_OPTIONS} /></Form.Item>
            <Form.Item label="发送范围" name="target_type"><Select disabled options={[{ value: 'configured_group', label: '当前钉钉默认群' }]} /></Form.Item>
          </div>
          <Form.Item label="消息正文" name="content" rules={[{ required: true, message: '请输入消息正文' }, { max: 5000, message: '正文不能超过5000字' }]}>
            <Input.TextArea
              data-testid="bot-broadcast-content"
              rows={6}
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
              <Button data-testid="bot-broadcast-save-draft" icon={<SaveOutlined />} loading={broadcastSaving} onClick={handleSaveDraft}>
                保存草稿
              </Button>
              <Popconfirm title="确认立即群发？" description="消息会发送到当前钉钉默认群，发送结果会写入记录。" okText="确认发送" cancelText="再检查" onConfirm={handleSendNow}>
                <Button type="primary" icon={<SendOutlined />} loading={broadcastSending}>确认发送</Button>
              </Popconfirm>
            </Space>
          </div>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection
        title="发送记录"
        description="失败草稿可以重新发送。"
        action={
          <Space wrap>
            <Select
              value={broadcastStatusFilter}
              style={{ width: 132 }}
              onChange={(value) => setBroadcastStatusFilter(value)}
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
        <Table
          className="edl-table bot-record-table"
          rowKey="id"
          dataSource={broadcasts}
          pagination={false}
          scroll={{ x: 980 }}
          locale={{ emptyText: <Empty description="暂无群发记录" /> }}
          columns={[
            {
              title: '消息',
              dataIndex: 'title',
              width: 300,
              render: (_: string, record: BotBroadcastItem) => (
                <div className="bot-table-title"><strong>{record.title}</strong><span>{record.content}</span></div>
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
            { title: '收件范围', dataIndex: 'target_summary', width: 190 },
            { title: '发送时间', dataIndex: 'sent_at', width: 170, render: formatTime },
            {
              title: '结果',
              dataIndex: 'result_message',
              render: (value: string, record: BotBroadcastItem) => (
                <Tooltip title={record.error_message || value || '暂无发送结果'}>
                  <span className={record.status === 'failed' ? 'bot-result is-error' : 'bot-result'}>{record.error_message || value || '—'}</span>
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
                  <Popconfirm title="确认发送这条消息？" description="消息会发送到当前钉钉默认群。" okText="发送" cancelText="取消" onConfirm={() => handleResend(record)}>
                    <Button size="small" icon={<SendOutlined />} loading={resendingId === record.id}>发送</Button>
                  </Popconfirm>
                );
              },
            },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
