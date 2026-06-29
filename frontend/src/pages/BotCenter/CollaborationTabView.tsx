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

export function renderCollaborationTab(ctx: BotCenterViewContext) {
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
      <WorkbenchSection title="多机器人协作" description="让多个机器人分别回答同一任务，再汇总证据和结论。">
        {!canEvaluate && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看协作结果。" />}
        <Form<CollaborationFormValues> form={collaborationForm} layout="vertical" disabled={!canEvaluate}>
          <div className="bot-form-row">
            <Form.Item label="协作标题" name="title">
              <Input placeholder="例如：本周公安空间数据机会会商" />
            </Form.Item>
            <Form.Item label="主机器人" name="lead_profile_key" rules={[{ required: true, message: '请选择主机器人' }]}>
              <Select options={profileOptions} />
            </Form.Item>
          </div>
          <Form.Item label="参与机器人" name="participant_profiles">
            <Select mode="multiple" options={profileOptions} placeholder="选择参与会商的机器人" />
          </Form.Item>
          <Form.Item label="协作任务" name="input_text" rules={[{ required: true, message: '请输入协作任务' }]}>
            <Input.TextArea rows={5} placeholder="例如：结合本周标讯、政策、部门周报，判断下周应重点跟进哪些方向" />
          </Form.Item>
          <Button type="primary" icon={<BranchesOutlined />} loading={collaborationRunning} onClick={handleRunCollaboration}>运行协作</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="协作结果" description="每次协作都会保留参与机器人、回答、证据和汇总结论。">
        {collaborations[0] ? (
          <div className="bot-preview-answer">
            <strong>{collaborations[0].title}</strong>
            <p>{String(collaborations[0].result_payload?.summary || '暂无汇总')}</p>
            <span>{collaborations[0].participant_profiles.length} 个机器人 · {collaborations[0].evidence_records?.length || 0} 条证据</span>
          </div>
        ) : <Empty description="暂无协作结果" />}
      </WorkbenchSection>

      <WorkbenchSection title="协作记录" description="用于复盘机器人之间的分工、证据和结果。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="run_id"
          dataSource={collaborations}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '任务', dataIndex: 'title', render: (_: string, record: BotCollaborationRun) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.input_text}</span></div> },
            { title: '主机器人', dataIndex: 'lead_profile_key', width: 180, render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '参与', dataIndex: 'participant_profiles', render: (value: string[]) => (value || []).map((item) => <Tag key={item}>{profiles.find((profile) => profile.profile_key === item)?.name || item}</Tag>) },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'completed' ? 'success' : 'processing'}>{value}</Tag> },
            { title: '证据', dataIndex: 'evidence_records', width: 90, render: (value: BotEvidenceRecord[]) => value?.length || 0 },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
