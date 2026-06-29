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

export function renderSkillsTab(ctx: BotCenterViewContext) {
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
    <div className="bot-config-grid">
      <WorkbenchSection title="机器人 Profile" description="定义机器人身份、默认角色、可调用 Skill 和运营状态。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看机器人配置。" />}
        <Form<ProfileFormValues> form={profileForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="机器人标识" name="profile_key" rules={[{ required: true, message: '请输入机器人标识' }]}>
              <Input placeholder="例如：market_intelligence_agent" />
            </Form.Item>
            <Form.Item label="机器人名称" name="name" rules={[{ required: true, message: '请输入机器人名称' }]}>
              <Input placeholder="例如：市场洞察机器人" />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="默认提问身份" name="default_role">
              <Input placeholder="例如：市场部管理者" />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select options={[{ value: 'enabled', label: '启用' }, { value: 'disabled', label: '停用' }]} />
            </Form.Item>
          </div>
          <Form.Item label="可调用 Skill" name="allowed_skills">
            <Select mode="multiple" options={skillOptions} placeholder="选择这个机器人能调用的 Skill" />
          </Form.Item>
          <Form.Item label="职责描述" name="description">
            <Input.TextArea rows={4} placeholder="面向业务管理者描述这个机器人负责什么、不能做什么" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveProfile}>保存机器人配置</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="Skill 管理" description="Skill 是机器人能力包；这里管理启停、契约、证据要求和最近运行。">
        <Table
          className="edl-table"
          rowKey="skill_key"
          dataSource={skills}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            {
              title: 'Skill',
              width: 260,
              render: (_: unknown, record: BotSkill) => (
                <div className="bot-table-title">
                  <strong>{record.name}</strong>
                  <span>{record.skill_key}</span>
                </div>
              ),
            },
            { title: '分类', dataIndex: 'category', width: 110, render: (value: string) => <Tag>{value}</Tag> },
            { title: '触发场景', dataIndex: 'trigger_scenarios', render: (value: string[]) => <span>{(value || []).join('；')}</span> },
            { title: '权限', dataIndex: 'required_permission', width: 150, render: (value: string) => value ? <Tag color="blue">{value}</Tag> : <Tag>无</Tag> },
            {
              title: '状态',
              width: 120,
              render: (_: unknown, record: BotSkill) => (
                <Switch
                  data-testid={`bot-skill-switch-${record.skill_key}`}
                  checked={record.enabled}
                  onChange={(checked) => handleToggleSkill(record, checked)}
                  disabled={!canConfigure}
                />
              ),
            },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
