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

export function renderReleaseTab(ctx: BotCenterViewContext) {
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
      <WorkbenchSection title="发布版本" description="把当前机器人 Profile、Skill 绑定和配置保存为版本，发布前默认运行评测门禁。">
        {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看发布版本。" />}
        <Form<ReleaseFormValues> form={releaseForm} layout="vertical" disabled={!canConfigure}>
          <div className="bot-form-row">
            <Form.Item label="机器人" name="profile_key" rules={[{ required: true, message: '请选择机器人' }]}>
              <Select options={profileOptions} />
            </Form.Item>
            <Form.Item label="发布环境" name="environment_key">
              <Select options={environments.map((item) => ({ value: item.environment_key, label: item.name }))} />
            </Form.Item>
          </div>
          <Form.Item label="变更说明" name="change_note">
            <Input.TextArea rows={4} placeholder="说明这次调整了哪些能力、知识或策略" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleCreateRelease}>创建版本</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="近 7 天观测" description="从 Skill 运行、入站事件和反馈队列观察机器人健康度。">
        <div className="bot-quality-strip">
          <span>Skill 调用 {observability?.skill_runs ?? 0}</span>
          <span>失败调用 {observability?.failed_skill_runs ?? 0}</span>
          <span>平均耗时 {Math.round(observability?.avg_skill_duration_ms ?? 0)}ms</span>
          <span>入站异常 {observability?.failed_inbound_events ?? 0}</span>
          <span>待处理反馈 {observability?.open_feedback ?? feedbackTotal}</span>
        </div>
        <Form<FeedbackFormValues> form={feedbackForm} layout="vertical" disabled={!canEvaluate}>
          <div className="bot-form-row">
            <Form.Item label="反馈类型" name="rating" rules={[{ required: true, message: '请选择反馈类型' }]}>
              <Select options={[
                { value: 'wrong', label: '回答不准确' },
                { value: 'unhelpful', label: '帮助有限' },
                { value: 'unsafe', label: '存在风险' },
                { value: 'helpful', label: '有帮助' },
              ]} />
            </Form.Item>
            <Form.Item label="关联机器人" name="profile_key">
              <Select allowClear options={profileOptions} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="会话编号" name="conversation_id">
              <Input placeholder={conversationId || '可为空，默认关联当前测试会话'} />
            </Form.Item>
            <Form.Item label="原因" name="reason">
              <Input placeholder="例如：证据不足、路由错误、口径不对" />
            </Form.Item>
          </div>
          <Form.Item label="反馈说明" name="comment">
            <Input.TextArea rows={3} placeholder="描述用户反馈或验收问题" />
          </Form.Item>
          <Button type="primary" icon={<AuditOutlined />} disabled={!canEvaluate} onClick={handleCreateFeedback}>记录反馈</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title={`版本列表（${releaseTotal}）`} description="发布、强制发布、回滚都会保留审计。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="version_id"
          dataSource={releases}
          pagination={false}
          scroll={{ x: 1180 }}
          columns={[
            { title: '版本', render: (_: unknown, record: BotReleaseVersion) => <div className="bot-table-title"><strong>V{record.version} · {profiles.find((item) => item.profile_key === record.profile_key)?.name || record.profile_key}</strong><span>{record.version_id}</span></div> },
            { title: '环境', dataIndex: 'environment_key', width: 100, render: (value: string) => <Tag>{value}</Tag> },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'released' ? 'success' : value === 'blocked' ? 'error' : value === 'rolled_back' ? 'default' : 'processing'}>{value}</Tag> },
            { title: '门禁', dataIndex: 'test_summary', width: 150, render: (value: Record<string, any>) => `${value?.total ?? 0} 个用例 / ${value?.failed ?? 0} 失败` },
            { title: '创建人', dataIndex: 'created_by_name', width: 120 },
            { title: '发布时间', dataIndex: 'published_at', width: 170, render: formatTime },
            {
              title: '操作',
              width: 250,
              render: (_: unknown, record: BotReleaseVersion) => (
                <Space wrap>
                  <Button size="small" loading={publishingVersionId === record.version_id} disabled={!canEvaluate || record.status === 'released'} onClick={() => handlePublishRelease(record)}>
                    发布
                  </Button>
                  <Popconfirm title="确认强制发布？" description="会跳过失败门禁，但仍保留审计记录。" okText="强制发布" cancelText="取消" onConfirm={() => handlePublishRelease(record, true)}>
                    <Button size="small" disabled={!canEvaluate || record.status === 'released'}>强制</Button>
                  </Popconfirm>
                  <Button size="small" danger loading={rollingBackVersionId === record.version_id} disabled={!canConfigure || record.status === 'rolled_back'} onClick={() => handleRollbackRelease(record)}>
                    回滚
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title="任务运行历史" description="自动任务每次运行都有独立记录、耗时、状态和结果。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="run_id"
          dataSource={taskRuns}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '运行编号', dataIndex: 'run_id', width: 180 },
            { title: '任务', dataIndex: 'task_id', width: 180 },
            { title: '机器人', dataIndex: 'profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'completed' ? 'success' : value === 'failed' ? 'error' : 'processing'}>{value}</Tag> },
            { title: '耗时', dataIndex: 'duration_ms', width: 100, render: (value: number) => `${value || 0} ms` },
            { title: '开始时间', dataIndex: 'started_at', width: 170, render: formatTime },
            { title: '结果', dataIndex: 'result_payload', render: (value: Record<string, any>) => value?.answer || value?.error_message || value?.status || '—' },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title={`反馈队列（${feedbackTotal}）`} description="反馈用于驱动知识补充、Skill 调整和评测用例沉淀。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="feedback_id"
          dataSource={feedbackItems}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '反馈', dataIndex: 'feedback_id', width: 170 },
            { title: '类型', dataIndex: 'rating', width: 120, render: (value: string) => <Tag color={value === 'helpful' ? 'success' : value === 'unsafe' ? 'error' : 'warning'}>{value}</Tag> },
            { title: '机器人', dataIndex: 'profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value || '—' },
            { title: '原因', dataIndex: 'reason', width: 150, render: (value: string) => value || '—' },
            { title: '说明', dataIndex: 'comment' },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'open' ? 'processing' : 'success'}>{value}</Tag> },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
