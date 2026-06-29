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

export function renderKnowledgeTab(ctx: BotCenterViewContext) {
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
    <div className="bot-knowledge-grid">
      <WorkbenchSection title="知识入库" description="支持文本、HTML、Markdown、TXT；入库后会切片并用于测试台检索。">
        {!canManageKnowledge && <Alert type="warning" showIcon message="当前账号只能查看知识，不能新增知识。" />}
        <Form<KnowledgeFormValues>
          form={knowledgeForm}
          layout="vertical"
          disabled={!canManageKnowledge}
          initialValues={DEFAULT_KNOWLEDGE_FORM}
        >
          <div className="bot-form-row">
            <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入知识标题' }]}>
              <Input data-testid="bot-knowledge-title" placeholder="例如：空间数据平台产品方案" />
            </Form.Item>
            <Form.Item label="分类" name="category">
              <Select options={KNOWLEDGE_CATEGORIES} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="归属机器人" name="owner_profile_key">
              <Select allowClear options={profileOptions} placeholder="不选表示所有机器人可用" />
            </Form.Item>
            <Form.Item label="可见范围" name="visibility_scope">
              <Select options={[
                { value: 'all_bots', label: '全部机器人' },
                { value: 'profile_only', label: '仅归属机器人' },
              ]} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="审核状态" name="review_status">
              <Select options={[
                { value: 'approved', label: '可用于回答' },
                { value: 'pending', label: '待审核' },
                { value: 'rejected', label: '不采用' },
              ]} />
            </Form.Item>
            <Form.Item label="标签" name="tags_input">
              <Input placeholder="用逗号分隔，例如：空间数据,公安,方案" />
            </Form.Item>
          </div>
          <Form.Item label="文本内容" name="text_content" rules={[{ required: !knowledgeFile, message: '请输入文本内容，或选择文件上传' }]}>
            <Input.TextArea
              data-testid="bot-knowledge-content"
              rows={7}
              placeholder="可直接粘贴制度、方案、行业资料、客户材料等文本"
            />
          </Form.Item>
          <Space wrap>
            <Button data-testid="bot-knowledge-save" icon={<SaveOutlined />} loading={knowledgeUploading} onClick={handleCreateKnowledge}>
              保存文本知识
            </Button>
            <Upload
              beforeUpload={(file) => {
                setKnowledgeFile(file as File);
                return false;
              }}
              maxCount={1}
              fileList={knowledgeFile ? [{ uid: '1', name: knowledgeFile.name, status: 'done' }] as any : []}
              onRemove={() => setKnowledgeFile(null)}
            >
              <Button icon={<CloudUploadOutlined />}>选择文件</Button>
            </Upload>
            <Button type="primary" loading={knowledgeUploading} onClick={handleUploadKnowledge}>上传并索引</Button>
          </Space>
        </Form>
      </WorkbenchSection>

      <WorkbenchSection title="检索测试" description="直接验证机器人能不能从知识空间找到依据。">
        <Space.Compact style={{ width: '100%' }}>
          <Input
            data-testid="bot-knowledge-search-input"
            value={knowledgeQuery}
            onChange={(event) => setKnowledgeQuery(event.target.value)}
            placeholder="输入检索问题"
          />
          <Button data-testid="bot-knowledge-search-button" type="primary" onClick={handleSearchKnowledge}>检索</Button>
        </Space.Compact>
        <EvidenceList evidence={knowledgeSearchResult} />
      </WorkbenchSection>

      <WorkbenchSection title="知识同步任务" description="把周报、制度、方案等资料形成可运行的同步任务；运行后写入知识空间。" className="bot-span-all">
        <Form<KnowledgeSyncFormValues> form={syncForm} layout="vertical" disabled={!canManageKnowledge}>
          <div className="bot-form-row">
            <Form.Item label="任务名称" name="name" rules={[{ required: true, message: '请输入任务名称' }]}>
              <Input placeholder="例如：部门周报 HTML 同步" />
            </Form.Item>
            <Form.Item label="来源类型" name="source_type">
              <Select options={[
                { value: 'manual_text', label: '手动文本' },
                { value: 'dingtalk_docs', label: '钉钉文档' },
                { value: 'shared_folder', label: '共享目录' },
              ]} />
            </Form.Item>
          </div>
          <div className="bot-form-row">
            <Form.Item label="知识分类" name="category">
              <Select options={KNOWLEDGE_CATEGORIES} />
            </Form.Item>
            <Form.Item label="同步频率" name="schedule_type">
              <Select options={[{ value: 'manual', label: '手动' }, { value: 'daily', label: '每日' }, { value: 'weekly', label: '每周' }]} />
            </Form.Item>
          </div>
          <Form.Item label="入库标题" name="title">
            <Input placeholder="不填则使用任务名称" />
          </Form.Item>
          <Form.Item label="同步文本" name="text_content">
            <Input.TextArea rows={5} placeholder="手动文本来源可直接粘贴内容；其他来源会先保存连接器任务。" />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleCreateSyncJob}>创建同步任务</Button>
        </Form>
        <Table
          className="edl-table bot-subtable"
          rowKey="job_id"
          dataSource={syncJobs}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '任务', dataIndex: 'name', render: (_: string, record: BotKnowledgeSyncJob) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.job_id}</span></div> },
            { title: '来源', dataIndex: 'source_type', width: 130, render: (value: string) => <Tag>{value}</Tag> },
            { title: '分类', dataIndex: 'category', width: 110 },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'enabled' ? 'success' : 'default'}>{value}</Tag> },
            { title: '上次运行', dataIndex: 'last_run_at', width: 170, render: formatTime },
            { title: '结果', dataIndex: 'result_payload', render: (value: Record<string, any>) => value?.message || value?.status || '—' },
            {
              title: '操作',
              width: 110,
              render: (_: unknown, record: BotKnowledgeSyncJob) => (
                <Button size="small" loading={syncRunningId === record.job_id} disabled={!canManageKnowledge} onClick={() => handleRunSyncJob(record)}>运行</Button>
              ),
            },
          ]}
        />
      </WorkbenchSection>

      <WorkbenchSection title="知识文件" description={`当前 ${knowledgeTotal} 份文件已入库。`} className="bot-span-all">
        <Table
          className="edl-table"
          rowKey="file_id"
          dataSource={knowledgeFiles}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            { title: '标题', dataIndex: 'title', render: (_: string, record: BotKnowledgeFile) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.tags?.join('、') || record.file_name || record.source_type}</span></div> },
            { title: '分类', dataIndex: 'category', width: 120, render: (value: string) => <Tag>{value}</Tag> },
            { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'indexed' ? 'success' : 'default'}>{value}</Tag> },
            { title: '审核', dataIndex: 'review_status', width: 120, render: (value: string) => <Tag color={value === 'approved' ? 'success' : value === 'pending' ? 'processing' : 'default'}>{value || 'approved'}</Tag> },
            { title: '范围', dataIndex: 'visibility_scope', width: 130, render: (value: string) => value || 'all_bots' },
            { title: '切片', dataIndex: 'chunk_count', width: 90 },
            { title: '上传人', dataIndex: 'uploaded_by', width: 120 },
            { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            {
              title: '操作',
              width: 170,
              render: (_: unknown, record: BotKnowledgeFile) => (
                <Space wrap>
                  <Button size="small" disabled={!canManageKnowledge || (record.review_status === 'approved' && record.status === 'indexed')} onClick={() => handleUpdateKnowledgeStatus(record, { status: 'indexed', review_status: 'approved' })}>启用</Button>
                  <Button size="small" disabled={!canManageKnowledge || record.status === 'archived'} onClick={() => handleUpdateKnowledgeStatus(record, { status: 'archived', review_status: 'rejected' })}>归档</Button>
                </Space>
              ),
            },
          ]}
        />
      </WorkbenchSection>
    </div>
  );
}
