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

export function renderEvaluationTab(ctx: BotCenterViewContext) {
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
      <WorkbenchSection title="评测用例" description="固定高频问题，检查机器人是否调用正确 Skill、是否给出证据。">
        {!canEvaluate && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看评测结果。" />}
        <div className="bot-quality-strip">
          <span>用例 {qualitySummary?.test_cases ?? testCases.length}</span>
          <span>失败 {qualitySummary?.failed_evaluation_runs ?? 0}</span>
          <span>无证据调用 {qualitySummary?.no_evidence_skill_runs ?? 0}</span>
        </div>
        <Form<TestCaseFormValues> form={testCaseForm} layout="vertical" disabled={!canEvaluate}>
          <div className="bot-form-row">
            <Form.Item label="用例名称" name="name" rules={[{ required: true, message: '请输入用例名称' }]}>
              <Input placeholder="例如：公安空间数据机会分析" />
            </Form.Item>
            <Form.Item label="机器人" name="profile_key" rules={[{ required: true, message: '请选择机器人' }]}>
              <Select options={profileOptions} />
            </Form.Item>
          </div>
          <Form.Item label="测试问题" name="input_text" rules={[{ required: true, message: '请输入测试问题' }]}>
            <Input.TextArea rows={4} placeholder="输入真实用户会问的问题" />
          </Form.Item>
          <Form.Item label="多轮上下文" name="conversation_turns_input">
            <Input.TextArea rows={4} placeholder="可选。每行一轮，例如：用户：上周有哪些机会；机器人：请看证据；用户：按公安方向展开" />
          </Form.Item>
          <div className="bot-form-row">
            <Form.Item label="期望 Skill" name="expected_skills">
              <Select mode="multiple" options={skillOptions} />
            </Form.Item>
            <Form.Item label="优先级" name="priority">
              <Select options={[{ value: 'P0', label: 'P0' }, { value: 'P1', label: 'P1' }, { value: 'P2', label: 'P2' }, { value: 'P3', label: 'P3' }]} />
            </Form.Item>
          </div>
          <Form.Item label="期望包含内容" name="expected_contains_input">
            <Input placeholder="用逗号分隔，例如：证据,建议,下一步动作" />
          </Form.Item>
          <Form.Item name="required_evidence" valuePropName="checked">
            <Switch checkedChildren="必须有证据" unCheckedChildren="不强制证据" />
          </Form.Item>
          <Button type="primary" icon={<AuditOutlined />} onClick={handleCreateTestCase}>创建评测用例</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="意图纠错" description="当机器人选错 Skill 时，把用户说法和期望 Skill 固化为纠错规则。">
        <Form<CorrectionFormValues> form={correctionForm} layout="vertical" disabled={!canEvaluate}>
          <Form.Item label="用户说法" name="phrase" rules={[{ required: true, message: '请输入用户说法' }]}>
            <Input placeholder="例如：空间类机会" />
          </Form.Item>
          <Form.Item label="适用机器人" name="profile_key">
            <Select allowClear options={profileOptions} />
          </Form.Item>
          <Form.Item label="期望 Skill" name="expected_skills" rules={[{ required: true, message: '请选择期望 Skill' }]}>
            <Select mode="multiple" options={skillOptions} />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={3} placeholder="说明为什么应该这样路由" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleCreateCorrection}>保存纠错</Button>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="评测用例列表" description="运行后会生成评测记录和失败原因。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="id"
          dataSource={testCases}
          pagination={false}
          scroll={{ x: 1080 }}
          columns={[
            { title: '用例', dataIndex: 'name', render: (_: string, record: BotTestCase) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.input_text}</span></div> },
            { title: '优先级', dataIndex: 'priority', width: 90, render: (value: string) => <Tag color={value === 'P0' ? 'error' : value === 'P1' ? 'warning' : 'default'}>{value}</Tag> },
            { title: '期望 Skill', dataIndex: 'expected_skills', render: (value: string[]) => (value || []).map((item) => <Tag key={item}>{skills.find((skill) => skill.skill_key === item)?.name || item}</Tag>) },
            { title: '轮次', dataIndex: 'conversation_turns', width: 90, render: (value: any[]) => value?.length || 1 },
            { title: '上次结果', dataIndex: 'last_result', width: 110, render: (value: Record<string, any>) => <Tag color={value?.status === 'passed' ? 'success' : value?.status === 'failed' ? 'error' : 'default'}>{value?.status || '未运行'}</Tag> },
            { title: '上次运行', dataIndex: 'last_run_at', width: 170, render: formatTime },
            { title: '操作', width: 100, render: (_: unknown, record: BotTestCase) => <Button size="small" loading={caseRunningId === record.id} disabled={!canEvaluate} onClick={() => handleRunCase(record)}>运行</Button> },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title="最近评测与纠错" description="失败评测用于驱动知识补充、Skill 调整或意图纠错。" className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="run_id"
          dataSource={evaluationRuns}
          pagination={false}
          scroll={{ x: 920 }}
          columns={[
            { title: '运行编号', dataIndex: 'run_id' },
            { title: '机器人', dataIndex: 'profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'passed' ? 'success' : 'error'}>{value}</Tag> },
            { title: '得分', dataIndex: 'score', width: 90, render: (value: number) => `${Math.round((value || 0) * 100)}%` },
            { title: '失败项', dataIndex: 'result_payload', render: (value: Record<string, any>) => (value?.failures || []).map((item: any) => <Tag color="error" key={item.type}>{item.type}</Tag>) },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
          ]}
        />
        <div className="bot-correction-list">
          {intentCorrections.slice(0, 8).map((item) => (
            <Tag key={item.id} color="blue">{item.phrase} → {(item.expected_skills || []).join('、')}</Tag>
          ))}
        </div>
      </WorkbenchSection>
    </div>
  );
}
