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

export function renderChatTab(ctx: BotCenterViewContext) {
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
    <div className="bot-chat-grid">
      <WorkbenchSection title="对话测试台" description="像真实用户一样提问，右侧展示本轮调用了哪些 Skill、命中了哪些证据。">
        <Spin spinning={loading || chatSending}>
          <div className="bot-chat-toolbar">
            <Select
              value={selectedProfile}
              options={profileOptions}
              onChange={(value) => {
                setSelectedProfile(value);
                const profile = profiles.find((item) => item.profile_key === value);
                setSimulatedRole(profile?.default_role || '经营管理者');
                handleNewConversation();
              }}
            />
            <Input
              value={simulatedRole}
              onChange={(event) => setSimulatedRole(event.target.value)}
              placeholder="测试用户身份"
            />
            <Button onClick={handleNewConversation}>清空会话</Button>
          </div>
          <div className="bot-chat-window">
            {chatMessages.length ? chatMessages.map((item) => (
              <div className={`bot-chat-message role-${item.role}`} key={`${item.role}-${item.id}-${item.created_at}`}>
                <span>{item.role === 'user' ? simulatedRole || '用户' : selectedProfileData?.name || '机器人'}</span>
                <p>{item.content}</p>
              </div>
            )) : <Empty description="输入问题后开始测试机器人能力" />}
          </div>
          <div className="bot-chat-input">
            <Input.TextArea
              data-testid="bot-chat-input"
              rows={4}
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="例如：分析一下今年公安、政数、空间数据相关标讯和政策机会"
            />
            <Button data-testid="bot-chat-send" type="primary" icon={<SendOutlined />} loading={chatSending} onClick={handleChatSend}>
              发送测试
            </Button>
          </div>
        </Spin>
      </WorkbenchSection>

      <div className="bot-agent-side">
        <WorkbenchSection title="本轮调用链" description="每次回答都必须能追踪 Skill 和证据。">
          {chatResult?.selected_skills?.length ? (
            <div className="bot-skill-trace">
              {chatResult.selected_skills.map((run) => (
                <div className="bot-trace-item" key={run.run_id}>
                  <div>
                    <strong>{run.skill_name || run.skill_key}</strong>
                    <Tag color={run.status === 'success' ? 'success' : 'error'}>{run.status}</Tag>
                  </div>
                  <span>{run.duration_ms ?? 0} ms · {run.evidence_records?.length || 0} 条证据</span>
                </div>
              ))}
            </div>
          ) : <Empty description="暂无调用链" />}
        </WorkbenchSection>

        <WorkbenchSection title="证据命中" description="关键结论必须来自这些证据。">
          <EvidenceList evidence={chatResult?.evidence_records || []} />
        </WorkbenchSection>
      </div>
    </div>
  );
}
