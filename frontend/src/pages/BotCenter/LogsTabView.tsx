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

export function renderLogsTab(ctx: BotCenterViewContext) {
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
    <div className="bot-logs-grid">
      <WorkbenchSection title="Skill 运行日志" description="每次 Skill 调用的状态、耗时和证据数量。">
        <Table
          className="edl-table"
          rowKey="run_id"
          dataSource={skillRuns}
          pagination={false}
          columns={[
            { title: 'Skill', dataIndex: 'skill_key' },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'success' ? 'success' : 'error'}>{value}</Tag> },
            { title: '证据', dataIndex: 'evidence_records', width: 90, render: (value: any[]) => value?.length || 0 },
            { title: '耗时', dataIndex: 'duration_ms', width: 100, render: (value: number) => `${value || 0} ms` },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
      <WorkbenchSection title="审计日志" description="配置、测试、知识入库等关键动作。">
        <Table
          className="edl-table"
          rowKey="id"
          dataSource={auditLogs}
          pagination={false}
          columns={[
            { title: '事件', dataIndex: 'event_type' },
            { title: '机器人', dataIndex: 'profile_key' },
            { title: '操作者', dataIndex: 'actor_name', width: 120 },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
