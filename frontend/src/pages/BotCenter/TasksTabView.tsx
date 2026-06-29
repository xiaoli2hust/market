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

export function renderTasksTab(ctx: BotCenterViewContext) {
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
      <WorkbenchSection title="自动任务" description="把市场简报、周报总结、商机跟进等工作配置成可运行任务。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看任务。" />}
        <Form<TaskFormValues> form={taskForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="任务名称" name="title" rules={[{ required: true, message: '请输入任务名称' }]}>
              <Input placeholder="例如：每周市场洞察简报" />
            </Form.Item>
            <Form.Item label="任务类型" name="task_type">
              <Select options={[
                { value: 'market_digest', label: '市场洞察简报' },
                { value: 'weekly_summary', label: '周报归档总结' },
                { value: 'opportunity_followup', label: '商机跟进提醒' },
                { value: 'custom_prompt', label: '自定义任务' },
              ]} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="执行机器人" name="profile_key" rules={[{ required: true, message: '请选择机器人' }]}>
              <Select options={profileOptions} />
            </Form.Item>
            <Form.Item label="调度方式" name="schedule_type">
              <Select options={[{ value: 'manual', label: '手动运行' }, { value: 'daily', label: '每日' }, { value: 'weekly', label: '每周' }]} />
            </Form.Item>
          </div>
          <Form.Item label="任务指令" name="prompt">
            <Input.TextArea rows={4} placeholder="不填写时使用任务类型内置指令；填写后按此指令运行" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleCreateTask}>创建任务</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="动作审批" description="机器人准备执行群发、外部调用等动作时，先进入审批队列。">
        {!canApprove && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号没有审批权限。" />}
        <Form<ApprovalFormValues> form={approvalForm} layout="vertical" disabled={!canApprove}>
          <div className="bot-form-row">
            <Form.Item label="动作标题" name="title" rules={[{ required: true, message: '请输入动作标题' }]}>
              <Input placeholder="例如：发送本周市场洞察摘要" />
            </Form.Item>
            <Form.Item label="动作类型" name="action_type">
              <Select options={[{ value: 'dingtalk_broadcast', label: '钉钉群发' }, { value: 'external_api', label: '外部接口' }, { value: 'data_update', label: '数据更新' }]} />
            </Form.Item>
          </div>
          <Form.Item label="关联机器人" name="profile_key">
            <Select allowClear options={profileOptions} />
          </Form.Item>
          <Form.Item label="动作内容" name="content">
            <Input.TextArea rows={4} placeholder="描述机器人希望执行什么动作，审批后仍会保留审计记录" />
          </Form.Item>
          <Button type="primary" icon={<AuditOutlined />} onClick={handleCreateApproval}>提交审批</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title={`任务列表（${taskTotal}）`} description="手动运行会真实调用机器人并写入运行结果。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="task_id"
          dataSource={tasks}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '任务', dataIndex: 'title', render: (_: string, record: BotTask) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.task_id}</span></div> },
            { title: '类型', dataIndex: 'task_type', width: 150, render: (value: string) => <Tag>{value}</Tag> },
            { title: '机器人', dataIndex: 'profile_key', width: 180, render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'enabled' ? 'success' : 'default'}>{value}</Tag> },
            { title: '上次运行', dataIndex: 'last_run_at', width: 170, render: formatTime },
            { title: '证据', dataIndex: 'result_payload', width: 90, render: (value: Record<string, any>) => value?.evidence_count ?? '—' },
            {
              title: '操作',
              width: 110,
              render: (_: unknown, record: BotTask) => (
                <Button size="small" icon={<ClockCircleOutlined />} loading={taskRunningId === record.task_id} disabled={!canConfigure} onClick={() => handleRunTask(record)}>
                  运行
                </Button>
              ),
            },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title={`审批队列（${approvalTotal}）`} description="通过、驳回、执行都会写入审计。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="action_id"
          dataSource={approvals}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '动作', dataIndex: 'title', render: (_: string, record: BotActionApproval) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.action_id}</span></div> },
            { title: '类型', dataIndex: 'action_type', width: 150, render: (value: string) => <Tag>{value}</Tag> },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'pending' ? 'processing' : value === 'approved' ? 'success' : value === 'rejected' ? 'error' : 'default'}>{value}</Tag> },
            { title: '申请人', dataIndex: 'requested_by_name', width: 120 },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            {
              title: '操作',
              width: 220,
              render: (_: unknown, record: BotActionApproval) => (
                <Space wrap>
                  <Button size="small" disabled={!canApprove || record.status !== 'pending'} onClick={() => handleDecideApproval(record, 'approve')}>通过</Button>
                  <Button size="small" danger disabled={!canApprove || record.status !== 'pending'} onClick={() => handleDecideApproval(record, 'reject')}>驳回</Button>
                  <Button size="small" type="primary" disabled={!canApprove || record.status !== 'approved'} onClick={() => handleDecideApproval(record, 'execute')}>执行</Button>
                </Space>
              ),
            },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
