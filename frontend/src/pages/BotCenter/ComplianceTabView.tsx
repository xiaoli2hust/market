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

export function renderComplianceTab(ctx: BotCenterViewContext) {
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
    <div className="bot-governance-grid">
      <WorkbenchSection title="运行环境" description="区分测试、预发布和生产环境，避免把未验证能力直接暴露给真实群聊。">
        <Table
          className="edl-table"
          rowKey="environment_key"
          dataSource={environments}
          pagination={false}
          columns={[
            { title: '环境', dataIndex: 'name', render: (_: string, record: BotEnvironment) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.environment_key}</span></div> },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
            { title: '默认', dataIndex: 'is_default', width: 80, render: (value: boolean) => value ? <Tag color="blue">默认</Tag> : <span className="bot-muted">—</span> },
            { title: '配置', dataIndex: 'config', render: (value: Record<string, any>) => <span>{Object.keys(value || {}).join('、') || '—'}</span> },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title="合规策略" description="配置内容安全、敏感词处理和留存策略；命中后会进入入站事件和收件箱。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看合规策略。" />}
        <Form<ComplianceFormValues> form={complianceForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="策略标识" name="policy_key">
              <Input placeholder="不填则自动生成；已有标识会更新策略" />
            </Form.Item>
            <Form.Item label="策略名称" name="name" rules={[{ required: true, message: '请输入策略名称' }]}>
              <Input placeholder="例如：外部消息敏感内容检查" />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="策略类型" name="policy_type">
              <Select options={[
                { value: 'content_guard', label: '内容安全' },
                { value: 'retention', label: '留存规则' },
                { value: 'permission', label: '权限边界' },
              ]} />
            </Form.Item>
            <Form.Item label="命中动作" name="action">
              <Select options={[
                { value: 'warn', label: '提醒并继续' },
                { value: 'block', label: '阻断处理' },
                { value: 'handoff', label: '转人工' },
              ]} />
            </Form.Item>
          </div>
          <Form.Item label="状态" name="status">
            <Select options={[{ value: 'enabled', label: '启用' }, { value: 'disabled', label: '停用' }]} />
          </Form.Item>
          <Form.Item label="敏感词" name="blocked_terms_input">
            <Input.TextArea rows={4} placeholder="用逗号或换行分隔，例如：密码,密钥,身份证" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveCompliancePolicy}>保存策略</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="策略列表" description="启用中的策略会参与入站消息安全检查。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="policy_key"
          dataSource={compliancePolicies}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '策略', dataIndex: 'name', render: (_: string, record: BotCompliancePolicy) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.policy_key}</span></div> },
            { title: '类型', dataIndex: 'policy_type', width: 130, render: (value: string) => <Tag>{value}</Tag> },
            { title: '动作', dataIndex: 'action', width: 110, render: (value: string) => <Tag color={value === 'block' ? 'error' : value === 'handoff' ? 'warning' : 'processing'}>{value}</Tag> },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'enabled' ? 'success' : 'default'}>{value}</Tag> },
            { title: '规则', dataIndex: 'rules', render: (value: Record<string, any>) => (value?.blocked_terms || []).map((item: string) => <Tag key={item}>{item}</Tag>) },
            { title: '时间', dataIndex: 'updated_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
