import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { history } from '@@/exports';
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
  Tabs,
  Tag,
  Tooltip,
  Upload,
  message,
} from 'antd';
import {
  ApiOutlined,
  AuditOutlined,
  BellOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FieldTimeOutlined,
  FileSearchOutlined,
  RobotOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  BotActionApproval,
  BotAuditLog,
  BotBroadcastItem,
  BotBroadcastPayload,
  BotBroadcastStatus,
  BotChannelAdapter,
  BotChannelBinding,
  BotChatTestResult,
  BotCollaborationRun,
  BotCompliancePolicy,
  BotEvidenceRecord,
  BotEvaluationRun,
  BotEnvironment,
  BotFeedback,
  BotHandoff,
  BotInboxItem,
  BotIntentCorrection,
  BotKnowledgeFile,
  BotKnowledgeSyncJob,
  BotMessage,
  BotMessageType,
  BotObservabilitySummary,
  BotOverview,
  BotProfile,
  BotQualitySummary,
  BotReleaseVersion,
  BotSkill,
  BotSkillRun,
  BotTask,
  BotTaskRun,
  BotTestCase,
  createBotApproval,
  createBotBroadcast,
  createBotChannelBinding,
  createBotFeedback,
  createBotHandoff,
  createBotIntentCorrection,
  createBotKnowledgeSyncJob,
  createBotKnowledgeText,
  createBotProfile,
  createBotRelease,
  createBotTask,
  createBotTestCase,
  decideBotApproval,
  fetchBotAuditLogs,
  fetchBotApprovals,
  fetchBotBroadcasts,
  fetchBotChannelAdapters,
  fetchBotChannelBindings,
  fetchBotCollaborations,
  fetchBotCompliancePolicies,
  fetchBotEnvironments,
  fetchBotConversations,
  fetchBotEvaluationRuns,
  fetchBotFeedback,
  fetchBotHandoffs,
  fetchBotInbox,
  fetchBotIntentCorrections,
  fetchBotKnowledgeFiles,
  fetchBotKnowledgeSyncJobs,
  fetchBotObservabilitySummary,
  fetchBotOverview,
  fetchBotProfiles,
  fetchBotQualitySummary,
  fetchBotReleases,
  fetchBotSkillRuns,
  fetchBotSkills,
  fetchBotTaskRuns,
  fetchBotTasks,
  fetchBotTestCases,
  getApiErrorMessage,
  getCurrentUser,
  publishBotRelease,
  rollbackBotRelease,
  runBotCollaboration,
  runBotChatTest,
  runBotInboundTest,
  runBotKnowledgeSyncJob,
  runBotTask,
  runBotTestCase,
  saveBotChannelAdapter,
  saveBotCompliancePolicy,
  searchBotKnowledge,
  sendBotBroadcast,
  sendExistingBotBroadcast,
  updateBotChannelBinding,
  updateBotInboxItem,
  updateBotKnowledgeFile,
  updateBotProfile,
  updateBotSkill,
  uploadBotKnowledgeFile,
  userHasPermission,
} from '@/services/api';
import {
  WorkbenchMetricGrid,
  WorkbenchPageHeader,
  WorkbenchSection,
  WorkbenchStatusRail,
} from '@/components/workbench';
import './bot-center.less';

const PAGE_SIZE = 10;

const STATUS_META: Record<BotBroadcastStatus, { label: string; color: string; icon: React.ReactNode }> = {
  draft: { label: '草稿', color: 'default', icon: <ClockCircleOutlined /> },
  sending: { label: '发送中', color: 'processing', icon: <FieldTimeOutlined /> },
  sent: { label: '已发送', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '发送失败', color: 'error', icon: <ExclamationCircleOutlined /> },
};

const NOTICE_TYPE_OPTIONS = [
  { value: 'general', label: '普通通知' },
  { value: 'daily_report', label: '日报周报' },
  { value: 'market_digest', label: '市场速递' },
  { value: 'bidding_alert', label: '标讯提醒' },
  { value: 'task_followup', label: '任务提醒' },
];

const MESSAGE_TYPE_OPTIONS: Array<{ value: BotMessageType; label: string }> = [
  { value: 'markdown', label: '图文排版' },
  { value: 'text', label: '纯文本' },
];

const DEFAULT_BROADCAST_FORM: Partial<BroadcastFormValues> = {
  message_type: 'markdown',
  notice_type: 'general',
  target_type: 'configured_group',
  at_all: false,
};

const DEFAULT_KNOWLEDGE_FORM: Partial<KnowledgeFormValues> = {
  category: 'general',
  visibility_scope: 'all_bots',
  review_status: 'approved',
};

const KNOWLEDGE_CATEGORIES = [
  { value: 'general', label: '通用资料' },
  { value: 'product', label: '产品方案' },
  { value: 'spatial_data', label: '空间数据' },
  { value: 'policy', label: '政策制度' },
  { value: 'weekly_report', label: '周报材料' },
  { value: 'customer', label: '客户资料' },
];

type BroadcastFormValues = BotBroadcastPayload & { notice_type?: string };
type KnowledgeFormValues = {
  title: string;
  category: string;
  text_content: string;
  owner_profile_key?: string;
  visibility_scope?: string;
  review_status?: string;
  tags_input?: string;
};
type ProfileFormValues = {
  profile_key: string;
  name: string;
  description?: string;
  default_role?: string;
  status?: string;
  allowed_skills?: string[];
};
type ChannelFormValues = {
  channel_key?: string;
  channel_name: string;
  channel_type?: string;
  bot_profile_key: string;
  external_id?: string;
  status?: string;
};
type AdapterFormValues = {
  adapter_key?: string;
  channel_type: string;
  name: string;
  status?: string;
  event_mode?: string;
  auth_scheme?: string;
  signing_required?: boolean;
  rate_limit_per_minute?: number;
  capabilities_input?: string;
};
type InboundFormValues = { channel_key?: string; sender_name?: string; content: string };
type HandoffFormValues = { inbox_id: string; assignee_name: string; reason?: string };
type TaskFormValues = {
  title: string;
  task_type?: string;
  profile_key: string;
  schedule_type?: string;
  prompt?: string;
};
type ApprovalFormValues = { title: string; action_type?: string; profile_key?: string; content?: string };
type TestCaseFormValues = {
  name: string;
  profile_key: string;
  input_text: string;
  conversation_turns_input?: string;
  expected_skills?: string[];
  expected_contains_input?: string;
  required_evidence?: boolean;
  priority?: string;
};
type CorrectionFormValues = { phrase: string; profile_key?: string; expected_skills?: string[]; notes?: string };
type CollaborationFormValues = {
  title?: string;
  lead_profile_key: string;
  participant_profiles?: string[];
  input_text: string;
};
type ReleaseFormValues = { profile_key: string; environment_key?: string; change_note?: string };
type FeedbackFormValues = {
  rating: string;
  profile_key?: string;
  conversation_id?: string;
  reason?: string;
  comment?: string;
};
type KnowledgeSyncFormValues = {
  name: string;
  source_type?: string;
  category?: string;
  schedule_type?: string;
  title?: string;
  text_content?: string;
};
type ComplianceFormValues = {
  policy_key?: string;
  name: string;
  policy_type?: string;
  status?: string;
  action?: string;
  blocked_terms_input?: string;
};

const BotCenter: React.FC = () => {
  const currentUser = getCurrentUser();
  const canConfigure = userHasPermission(currentUser, 'bot:configure');
  const canManageKnowledge = userHasPermission(currentUser, 'bot:knowledge');
  const canApprove = userHasPermission(currentUser, 'bot:approve');
  const canEvaluate = userHasPermission(currentUser, 'bot:evaluate');
  const canBroadcast = userHasPermission(currentUser, 'bot:broadcast');
  const [activeTab, setActiveTab] = useState('chat');
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState<BotOverview | null>(null);
  const [profiles, setProfiles] = useState<BotProfile[]>([]);
  const [skills, setSkills] = useState<BotSkill[]>([]);
  const [selectedProfile, setSelectedProfile] = useState('management_assistant_agent');

  const [chatInput, setChatInput] = useState('');
  const [simulatedRole, setSimulatedRole] = useState('经营管理者');
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [chatMessages, setChatMessages] = useState<BotMessage[]>([]);
  const [chatResult, setChatResult] = useState<BotChatTestResult | null>(null);
  const [chatSending, setChatSending] = useState(false);

  const [broadcastForm] = Form.useForm<BroadcastFormValues>();
  const [broadcasts, setBroadcasts] = useState<BotBroadcastItem[]>([]);
  const [broadcastTotal, setBroadcastTotal] = useState(0);
  const [broadcastStatusFilter, setBroadcastStatusFilter] = useState<BotBroadcastStatus | 'all'>('all');
  const [broadcastSaving, setBroadcastSaving] = useState(false);
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [resendingId, setResendingId] = useState<number | null>(null);

  const [knowledgeForm] = Form.useForm<KnowledgeFormValues>();
  const [knowledgeFiles, setKnowledgeFiles] = useState<BotKnowledgeFile[]>([]);
  const [knowledgeTotal, setKnowledgeTotal] = useState(0);
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [knowledgeUploading, setKnowledgeUploading] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState('');
  const [knowledgeSearchResult, setKnowledgeSearchResult] = useState<BotEvidenceRecord[]>([]);

  const [profileForm] = Form.useForm<ProfileFormValues>();
  const [channelForm] = Form.useForm<ChannelFormValues>();
  const [adapterForm] = Form.useForm<AdapterFormValues>();
  const [inboundForm] = Form.useForm<InboundFormValues>();
  const [handoffForm] = Form.useForm<HandoffFormValues>();
  const [taskForm] = Form.useForm<TaskFormValues>();
  const [approvalForm] = Form.useForm<ApprovalFormValues>();
  const [testCaseForm] = Form.useForm<TestCaseFormValues>();
  const [correctionForm] = Form.useForm<CorrectionFormValues>();
  const [collaborationForm] = Form.useForm<CollaborationFormValues>();
  const [releaseForm] = Form.useForm<ReleaseFormValues>();
  const [feedbackForm] = Form.useForm<FeedbackFormValues>();
  const [syncForm] = Form.useForm<KnowledgeSyncFormValues>();
  const [complianceForm] = Form.useForm<ComplianceFormValues>();
  const [bindings, setBindings] = useState<BotChannelBinding[]>([]);
  const [adapters, setAdapters] = useState<BotChannelAdapter[]>([]);
  const [inboxItems, setInboxItems] = useState<BotInboxItem[]>([]);
  const [inboxTotal, setInboxTotal] = useState(0);
  const [handoffs, setHandoffs] = useState<BotHandoff[]>([]);
  const [handoffTotal, setHandoffTotal] = useState(0);
  const [skillRuns, setSkillRuns] = useState<BotSkillRun[]>([]);
  const [auditLogs, setAuditLogs] = useState<BotAuditLog[]>([]);
  const [inboundResult, setInboundResult] = useState<BotChatTestResult | null>(null);
  const [tasks, setTasks] = useState<BotTask[]>([]);
  const [taskTotal, setTaskTotal] = useState(0);
  const [taskRuns, setTaskRuns] = useState<BotTaskRun[]>([]);
  const [taskRunningId, setTaskRunningId] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<BotActionApproval[]>([]);
  const [approvalTotal, setApprovalTotal] = useState(0);
  const [testCases, setTestCases] = useState<BotTestCase[]>([]);
  const [evaluationRuns, setEvaluationRuns] = useState<BotEvaluationRun[]>([]);
  const [intentCorrections, setIntentCorrections] = useState<BotIntentCorrection[]>([]);
  const [caseRunningId, setCaseRunningId] = useState<number | null>(null);
  const [collaborations, setCollaborations] = useState<BotCollaborationRun[]>([]);
  const [collaborationRunning, setCollaborationRunning] = useState(false);
  const [qualitySummary, setQualitySummary] = useState<BotQualitySummary | null>(null);
  const [releases, setReleases] = useState<BotReleaseVersion[]>([]);
  const [releaseTotal, setReleaseTotal] = useState(0);
  const [publishingVersionId, setPublishingVersionId] = useState<string | null>(null);
  const [rollingBackVersionId, setRollingBackVersionId] = useState<string | null>(null);
  const [feedbackItems, setFeedbackItems] = useState<BotFeedback[]>([]);
  const [feedbackTotal, setFeedbackTotal] = useState(0);
  const [syncJobs, setSyncJobs] = useState<BotKnowledgeSyncJob[]>([]);
  const [syncRunningId, setSyncRunningId] = useState<string | null>(null);
  const [environments, setEnvironments] = useState<BotEnvironment[]>([]);
  const [compliancePolicies, setCompliancePolicies] = useState<BotCompliancePolicy[]>([]);
  const [observability, setObservability] = useState<BotObservabilitySummary | null>(null);

  const loadCore = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewResp, profileResp, skillResp] = await Promise.all([
        fetchBotOverview(),
        fetchBotProfiles(),
        fetchBotSkills(),
      ]);
      setOverview(overviewResp);
      setProfiles(profileResp || []);
      setSkills(skillResp || []);
      if (!selectedProfile && profileResp?.[0]?.profile_key) {
        setSelectedProfile(profileResp[0].profile_key);
      }
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载机器人配置失败'));
    } finally {
      setLoading(false);
    }
  }, [selectedProfile]);

  const loadBroadcasts = useCallback(async () => {
    try {
      const resp = await fetchBotBroadcasts({
        page: 1,
        page_size: PAGE_SIZE,
        status: broadcastStatusFilter === 'all' ? undefined : broadcastStatusFilter,
      });
      setBroadcasts(resp?.items || []);
      setBroadcastTotal(resp?.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载群发记录失败'));
    }
  }, [broadcastStatusFilter]);

  const loadKnowledge = useCallback(async () => {
    try {
      const resp = await fetchBotKnowledgeFiles({ page: 1, page_size: PAGE_SIZE });
      setKnowledgeFiles(resp?.items || []);
      setKnowledgeTotal(resp?.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载知识空间失败'));
    }
  }, []);

  const loadOps = useCallback(async () => {
    try {
      const [bindingResp, runResp, auditResp, adapterResp, inboxResp, handoffResp] = await Promise.all([
        fetchBotChannelBindings(),
        fetchBotSkillRuns({ page: 1, page_size: PAGE_SIZE }),
        fetchBotAuditLogs({ page: 1, page_size: PAGE_SIZE }),
        fetchBotChannelAdapters(),
        fetchBotInbox(),
        fetchBotHandoffs(),
      ]);
      setBindings(bindingResp || []);
      setSkillRuns(runResp?.items || []);
      setAuditLogs(auditResp?.items || []);
      setAdapters(adapterResp || []);
      setInboxItems(inboxResp?.items || []);
      setInboxTotal(inboxResp?.total || 0);
      setHandoffs(handoffResp?.items || []);
      setHandoffTotal(handoffResp?.total || 0);
    } catch {
      // 局部日志加载失败不影响对话台。
    }
  }, []);

  const loadGovernance = useCallback(async () => {
    try {
      const [
        taskResp,
        approvalResp,
        caseResp,
        evalResp,
        correctionResp,
        collaborationResp,
        qualityResp,
        taskRunResp,
        releaseResp,
        feedbackResp,
        syncResp,
        environmentResp,
        complianceResp,
        observabilityResp,
      ] = await Promise.all([
        fetchBotTasks({ page: 1, page_size: PAGE_SIZE }),
        fetchBotApprovals({ page: 1, page_size: PAGE_SIZE }),
        fetchBotTestCases({ page: 1, page_size: PAGE_SIZE }),
        fetchBotEvaluationRuns({ page: 1, page_size: PAGE_SIZE }),
        fetchBotIntentCorrections(),
        fetchBotCollaborations({ page: 1, page_size: PAGE_SIZE }),
        fetchBotQualitySummary(),
        fetchBotTaskRuns(),
        fetchBotReleases(),
        fetchBotFeedback(),
        fetchBotKnowledgeSyncJobs(),
        fetchBotEnvironments(),
        fetchBotCompliancePolicies(),
        fetchBotObservabilitySummary(),
      ]);
      setTasks(taskResp?.items || []);
      setTaskTotal(taskResp?.total || 0);
      setApprovals(approvalResp?.items || []);
      setApprovalTotal(approvalResp?.total || 0);
      setTestCases(caseResp?.items || []);
      setEvaluationRuns(evalResp?.items || []);
      setIntentCorrections(correctionResp || []);
      setCollaborations(collaborationResp?.items || []);
      setQualitySummary(qualityResp || null);
      setTaskRuns(taskRunResp?.items || []);
      setReleases(releaseResp?.items || []);
      setReleaseTotal(releaseResp?.total || 0);
      setFeedbackItems(feedbackResp?.items || []);
      setFeedbackTotal(feedbackResp?.total || 0);
      setSyncJobs(syncResp?.items || []);
      setEnvironments(environmentResp || []);
      setCompliancePolicies(complianceResp || []);
      setObservability(observabilityResp || null);
    } catch {
      // 治理信息加载失败时保留主对话能力。
    }
  }, []);

  useEffect(() => {
    loadCore();
    loadBroadcasts();
    loadKnowledge();
    loadOps();
    loadGovernance();
  }, [loadBroadcasts, loadCore, loadGovernance, loadKnowledge, loadOps]);

  const selectedProfileData = useMemo(
    () => profiles.find((item) => item.profile_key === selectedProfile),
    [profiles, selectedProfile],
  );

  const boundSkills = useMemo(() => {
    const allowed = new Set(selectedProfileData?.allowed_skills || []);
    return skills.filter((skill) => allowed.has(skill.skill_key));
  }, [selectedProfileData, skills]);

  useEffect(() => {
    if (!selectedProfileData) return;
    profileForm.setFieldsValue({
      profile_key: selectedProfileData.profile_key,
      name: selectedProfileData.name,
      description: selectedProfileData.description || '',
      default_role: selectedProfileData.default_role || '经营管理者',
      status: selectedProfileData.status || 'enabled',
      allowed_skills: selectedProfileData.allowed_skills || [],
    });
    channelForm.setFieldsValue({ bot_profile_key: selectedProfileData.profile_key, channel_type: 'dingtalk', status: 'active' });
    adapterForm.setFieldsValue({
      channel_type: 'dingtalk',
      event_mode: 'webhook',
      auth_scheme: 'signed_webhook',
      status: 'enabled',
      signing_required: true,
      rate_limit_per_minute: 60,
    });
    handoffForm.setFieldsValue({ assignee_name: currentUser?.name || '' });
    taskForm.setFieldsValue({ profile_key: selectedProfileData.profile_key, schedule_type: 'manual', task_type: 'market_digest' });
    approvalForm.setFieldsValue({ profile_key: selectedProfileData.profile_key, action_type: 'dingtalk_broadcast' });
    testCaseForm.setFieldsValue({ profile_key: selectedProfileData.profile_key, priority: 'P1', required_evidence: true });
    correctionForm.setFieldsValue({ profile_key: selectedProfileData.profile_key });
    releaseForm.setFieldsValue({ profile_key: selectedProfileData.profile_key, environment_key: 'prod' });
    feedbackForm.setFieldsValue({ profile_key: selectedProfileData.profile_key, rating: 'wrong' });
    syncForm.setFieldsValue({ category: 'general', source_type: 'manual_text', schedule_type: 'manual' });
    complianceForm.setFieldsValue({ policy_type: 'content_guard', status: 'enabled', action: 'warn' });
    collaborationForm.setFieldsValue({
      lead_profile_key: selectedProfileData.profile_key,
      participant_profiles: profiles
        .filter((item) => item.profile_key !== selectedProfileData.profile_key)
        .slice(0, 3)
        .map((item) => item.profile_key),
    });
  }, [
    adapterForm,
    approvalForm,
    channelForm,
    collaborationForm,
    complianceForm,
    correctionForm,
    currentUser?.name,
    feedbackForm,
    handoffForm,
    profileForm,
    profiles,
    releaseForm,
    selectedProfileData,
    syncForm,
    taskForm,
    testCaseForm,
  ]);

  const handleChatSend = async () => {
    const text = chatInput.trim();
    if (!text) {
      message.warning('请输入测试问题');
      return;
    }
    setChatSending(true);
    try {
      const result = await runBotChatTest({
        profile_key: selectedProfile,
        message: text,
        conversation_id: conversationId,
        simulated_user_role: simulatedRole,
      });
      setConversationId(result.conversation.conversation_id);
      setChatResult(result);
      setChatMessages((prev) => [...prev, result.user_message, result.assistant_message]);
      setChatInput('');
      await Promise.all([loadCore(), loadOps()]);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '对话测试失败'));
    } finally {
      setChatSending(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(undefined);
    setChatMessages([]);
    setChatResult(null);
  };

  const handleToggleSkill = async (skill: BotSkill, enabled: boolean) => {
    if (!canConfigure) return;
    try {
      const updated = await updateBotSkill(skill.skill_key, { enabled });
      setSkills((prev) => prev.map((item) => item.skill_key === updated.skill_key ? updated : item));
      message.success(enabled ? 'Skill 已启用' : 'Skill 已停用');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '更新 Skill 失败'));
    }
  };

  const handleSaveProfile = async () => {
    if (!canConfigure) return;
    try {
      const values = await profileForm.validateFields();
      const payload = {
        profile_key: values.profile_key?.trim(),
        name: values.name?.trim(),
        description: values.description?.trim(),
        default_role: values.default_role?.trim(),
        status: values.status || 'active',
        allowed_skills: values.allowed_skills || [],
      };
      const exists = profiles.some((item) => item.profile_key === payload.profile_key);
      const saved = exists
        ? await updateBotProfile(payload.profile_key, payload)
        : await createBotProfile(payload);
      setSelectedProfile(saved.profile_key);
      await loadCore();
      message.success(exists ? '机器人配置已更新' : '机器人 Profile 已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存机器人配置失败'));
    }
  };

  const handleSaveChannelBinding = async () => {
    if (!canConfigure) return;
    try {
      const values = await channelForm.validateFields();
      const payload = {
        channel_key: values.channel_key?.trim(),
        channel_name: values.channel_name.trim(),
        channel_type: values.channel_type || 'dingtalk',
        bot_profile_key: values.bot_profile_key || selectedProfile,
        external_id: values.external_id?.trim(),
        status: values.status || 'active',
        binding_config: { source: '机器人中心配置' },
      };
      const exists = payload.channel_key
        ? bindings.some((item) => item.channel_key === payload.channel_key)
        : false;
      if (exists && payload.channel_key) {
        await updateBotChannelBinding(payload.channel_key, payload);
      } else {
        await createBotChannelBinding(payload);
      }
      channelForm.resetFields(['channel_key', 'channel_name', 'external_id']);
      await loadOps();
      message.success(exists ? '群聊绑定已更新' : '群聊绑定已新增');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存群聊绑定失败'));
    }
  };

  const handleSaveAdapter = async () => {
    if (!canConfigure) return;
    try {
      const values = await adapterForm.validateFields();
      await saveBotChannelAdapter({
        adapter_key: values.adapter_key?.trim(),
        channel_type: values.channel_type,
        name: values.name.trim(),
        status: values.status || 'enabled',
        event_mode: values.event_mode || 'webhook',
        auth_scheme: values.auth_scheme || 'signed_webhook',
        signing_required: values.signing_required !== false,
        rate_limit_per_minute: Number(values.rate_limit_per_minute || 60),
        capabilities: splitTextList(values.capabilities_input),
      });
      adapterForm.resetFields(['adapter_key', 'name', 'capabilities_input']);
      await Promise.all([loadCore(), loadOps()]);
      message.success('渠道适配器已保存');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存渠道适配器失败'));
    }
  };

  const handleInboundTest = async () => {
    try {
      const values = await inboundForm.validateFields();
      const result = await runBotInboundTest({
        channel_key: values.channel_key || bindings[0]?.channel_key || 'dingtalk_default',
        sender_name: values.sender_name || currentUser?.name || '测试用户',
        content: values.content.trim(),
      });
      setInboundResult(result);
      await Promise.all([loadCore(), loadOps()]);
      message.success('群聊入站测试完成');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '群聊入站测试失败'));
    }
  };

  const handleUpdateInboxStatus = async (record: BotInboxItem, status: string) => {
    if (!canApprove) return;
    try {
      await updateBotInboxItem(record.inbox_id, {
        status,
        owner_name: currentUser?.name,
        resolution_summary: status === 'resolved' ? '已在机器人中心处理完成' : record.resolution_summary || undefined,
      });
      await Promise.all([loadCore(), loadOps()]);
      message.success('收件箱状态已更新');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '更新收件箱失败'));
    }
  };

  const handleCreateHandoff = async () => {
    if (!canApprove) return;
    try {
      const values = await handoffForm.validateFields();
      await createBotHandoff(values.inbox_id, {
        assignee_name: values.assignee_name.trim(),
        reason: values.reason?.trim(),
      });
      handoffForm.resetFields(['inbox_id', 'reason']);
      handoffForm.setFieldsValue({ assignee_name: currentUser?.name || '' });
      await Promise.all([loadCore(), loadOps()]);
      message.success('已创建人工接管记录');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建人工接管失败'));
    }
  };

  const handleCreateTask = async () => {
    if (!canConfigure) return;
    try {
      const values = await taskForm.validateFields();
      await createBotTask({
        title: values.title.trim(),
        task_type: values.task_type || 'custom_prompt',
        profile_key: values.profile_key || selectedProfile,
        schedule_type: values.schedule_type || 'manual',
        input_payload: values.prompt ? { prompt: values.prompt.trim() } : {},
      });
      taskForm.resetFields(['title', 'prompt']);
      await Promise.all([loadCore(), loadGovernance(), loadOps()]);
      message.success('机器人任务已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建任务失败'));
    }
  };

  const handleRunTask = async (record: BotTask) => {
    if (!canConfigure) return;
    setTaskRunningId(record.task_id);
    try {
      await runBotTask(record.task_id);
      await Promise.all([loadCore(), loadGovernance(), loadOps()]);
      message.success('任务已运行，结果已写入任务记录');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '运行任务失败'));
    } finally {
      setTaskRunningId(null);
    }
  };

  const handleCreateApproval = async () => {
    if (!canApprove) return;
    try {
      const values = await approvalForm.validateFields();
      await createBotApproval({
        title: values.title.trim(),
        action_type: values.action_type || 'dingtalk_broadcast',
        profile_key: values.profile_key || selectedProfile,
        payload: { content: values.content?.trim() || '', created_from: 'bot_center' },
      });
      approvalForm.resetFields(['title', 'content']);
      await loadGovernance();
      message.success('待审批动作已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建审批动作失败'));
    }
  };

  const handleDecideApproval = async (record: BotActionApproval, decision: 'approve' | 'reject' | 'execute') => {
    if (!canApprove) return;
    try {
      await decideBotApproval(record.action_id, decision);
      await Promise.all([loadCore(), loadGovernance()]);
      message.success(decision === 'approve' ? '已通过审批' : decision === 'reject' ? '已驳回' : '已标记执行');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '审批操作失败'));
    }
  };

  const handleCreateTestCase = async () => {
    if (!canEvaluate) return;
    try {
      const values = await testCaseForm.validateFields();
      await createBotTestCase({
        name: values.name.trim(),
        profile_key: values.profile_key || selectedProfile,
        input_text: values.input_text.trim(),
        conversation_turns: parseConversationTurns(values.conversation_turns_input),
        expected_skills: values.expected_skills || [],
        expected_contains: splitTextList(values.expected_contains_input),
        required_evidence: values.required_evidence !== false,
        priority: values.priority || 'P1',
      });
      testCaseForm.resetFields(['name', 'input_text', 'conversation_turns_input', 'expected_contains_input', 'expected_skills']);
      await loadGovernance();
      message.success('评测用例已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建评测用例失败'));
    }
  };

  const handleRunCase = async (record: BotTestCase) => {
    if (!canEvaluate) return;
    setCaseRunningId(record.id);
    try {
      const result = await runBotTestCase(record.id);
      await Promise.all([loadCore(), loadGovernance(), loadOps()]);
      if (result.run.status === 'passed') message.success('评测通过');
      else message.warning('评测未通过，请查看失败项并补充纠错或知识');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '运行评测失败'));
    } finally {
      setCaseRunningId(null);
    }
  };

  const handleCreateCorrection = async () => {
    if (!canEvaluate) return;
    try {
      const values = await correctionForm.validateFields();
      await createBotIntentCorrection({
        phrase: values.phrase.trim(),
        profile_key: values.profile_key || selectedProfile,
        expected_skills: values.expected_skills || [],
        notes: values.notes?.trim(),
      });
      correctionForm.resetFields(['phrase', 'expected_skills', 'notes']);
      await loadGovernance();
      message.success('意图纠错已生效');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存意图纠错失败'));
    }
  };

  const handleRunCollaboration = async () => {
    if (!canEvaluate) return;
    setCollaborationRunning(true);
    try {
      const values = await collaborationForm.validateFields();
      await runBotCollaboration({
        title: values.title?.trim(),
        lead_profile_key: values.lead_profile_key || selectedProfile,
        participant_profiles: values.participant_profiles || [],
        input_text: values.input_text.trim(),
      });
      collaborationForm.resetFields(['title', 'input_text']);
      await Promise.all([loadCore(), loadGovernance(), loadOps()]);
      message.success('多机器人协作已完成');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '运行协作失败'));
    } finally {
      setCollaborationRunning(false);
    }
  };

  const handleUpdateKnowledgeStatus = async (record: BotKnowledgeFile, payload: Partial<BotKnowledgeFile>) => {
    if (!canManageKnowledge) return;
    try {
      await updateBotKnowledgeFile(record.file_id, payload);
      await loadKnowledge();
      message.success('知识状态已更新');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '更新知识状态失败'));
    }
  };

  const buildBroadcastPayload = async (): Promise<BotBroadcastPayload> => {
    const values = await broadcastForm.validateFields();
    return {
      title: values.title.trim(),
      content: values.content.trim(),
      message_type: values.message_type || 'markdown',
      target_type: 'configured_group',
      at_all: Boolean(values.at_all),
      target_payload: {
        notice_type: values.notice_type || 'general',
        requested_by: currentUser?.name || currentUser?.role || '系统用户',
      },
    };
  };

  const resetBroadcastForm = () => {
    broadcastForm.resetFields();
    broadcastForm.setFieldsValue(DEFAULT_BROADCAST_FORM);
  };

  const handleSaveDraft = async () => {
    if (!canBroadcast) return;
    setBroadcastSaving(true);
    try {
      await createBotBroadcast(await buildBroadcastPayload());
      resetBroadcastForm();
      setBroadcastStatusFilter('all');
      await loadBroadcasts();
      message.success('群发草稿已保存');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存草稿失败'));
    } finally {
      setBroadcastSaving(false);
    }
  };

  const handleSendNow = async () => {
    if (!canBroadcast) return;
    setBroadcastSending(true);
    try {
      const result = await sendBotBroadcast(await buildBroadcastPayload());
      resetBroadcastForm();
      setBroadcastStatusFilter('all');
      await loadBroadcasts();
      if (result.status === 'sent') message.success('消息已发送到钉钉群');
      else message.error(result.error_message || result.result_message || '消息发送失败');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '发送失败'));
    } finally {
      setBroadcastSending(false);
    }
  };

  const handleResend = async (record: BotBroadcastItem) => {
    if (!canBroadcast) return;
    setResendingId(record.id);
    try {
      const result = await sendExistingBotBroadcast(record.id);
      await loadBroadcasts();
      if (result.status === 'sent') message.success('消息已重新发送');
      else message.error(result.error_message || result.result_message || '重新发送失败');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '重新发送失败'));
    } finally {
      setResendingId(null);
    }
  };

  const handleCreateKnowledge = async () => {
    if (!canManageKnowledge) return;
    setKnowledgeUploading(true);
    try {
      const values = await knowledgeForm.validateFields();
      await createBotKnowledgeText({
        title: values.title.trim(),
        category: values.category || 'general',
        text_content: values.text_content?.trim() || '',
        owner_profile_key: values.owner_profile_key,
        visibility_scope: values.visibility_scope || 'all_bots',
        review_status: values.review_status || 'approved',
        tags: splitTextList(values.tags_input),
      });
      knowledgeForm.resetFields();
      knowledgeForm.setFieldsValue(DEFAULT_KNOWLEDGE_FORM);
      await loadKnowledge();
      message.success('知识文本已入库并切片');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识入库失败'));
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const handleUploadKnowledge = async () => {
    if (!canManageKnowledge || !knowledgeFile) {
      message.warning('请选择要上传的知识文件');
      return;
    }
    setKnowledgeUploading(true);
    try {
      const title = knowledgeForm.getFieldValue('title') || knowledgeFile.name;
      const category = knowledgeForm.getFieldValue('category') || 'general';
      const saved = await uploadBotKnowledgeFile({ title, category, file: knowledgeFile });
      await updateBotKnowledgeFile(saved.file_id, {
        owner_profile_key: knowledgeForm.getFieldValue('owner_profile_key'),
        visibility_scope: knowledgeForm.getFieldValue('visibility_scope') || 'all_bots',
        review_status: knowledgeForm.getFieldValue('review_status') || 'approved',
        tags: splitTextList(knowledgeForm.getFieldValue('tags_input')),
      });
      setKnowledgeFile(null);
      await loadKnowledge();
      message.success('知识文件已上传并建立索引');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识文件上传失败'));
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const handleSearchKnowledge = async () => {
    if (!knowledgeQuery.trim()) {
      message.warning('请输入检索问题');
      return;
    }
    try {
      const resp = await searchBotKnowledge(knowledgeQuery.trim());
      setKnowledgeSearchResult(resp.evidence_records || []);
      message.success(`命中 ${resp.evidence_records?.length || 0} 条证据`);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识检索失败'));
    }
  };

  const handleCreateSyncJob = async () => {
    if (!canManageKnowledge) return;
    try {
      const values = await syncForm.validateFields();
      await createBotKnowledgeSyncJob({
        name: values.name.trim(),
        source_type: values.source_type || 'manual_text',
        category: values.category || 'general',
        schedule_type: values.schedule_type || 'manual',
        source_config: {
          title: values.title?.trim() || values.name.trim(),
          text_content: values.text_content?.trim() || '',
        },
      });
      syncForm.resetFields(['name', 'title', 'text_content']);
      syncForm.setFieldsValue({ category: 'general', source_type: 'manual_text', schedule_type: 'manual' });
      await Promise.all([loadKnowledge(), loadGovernance()]);
      message.success('知识同步任务已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建知识同步任务失败'));
    }
  };

  const handleRunSyncJob = async (record: BotKnowledgeSyncJob) => {
    if (!canManageKnowledge) return;
    setSyncRunningId(record.job_id);
    try {
      const result = await runBotKnowledgeSyncJob(record.job_id);
      await Promise.all([loadKnowledge(), loadGovernance()]);
      message.success(result.result_payload?.message || '知识同步任务已运行');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '运行知识同步失败'));
    } finally {
      setSyncRunningId(null);
    }
  };

  const handleCreateRelease = async () => {
    if (!canConfigure) return;
    try {
      const values = await releaseForm.validateFields();
      await createBotRelease({
        profile_key: values.profile_key || selectedProfile,
        environment_key: values.environment_key || 'prod',
        change_note: values.change_note?.trim(),
      });
      releaseForm.resetFields(['change_note']);
      await loadGovernance();
      message.success('发布版本已创建');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '创建发布版本失败'));
    }
  };

  const handlePublishRelease = async (record: BotReleaseVersion, force = false) => {
    if (!canEvaluate) return;
    setPublishingVersionId(record.version_id);
    try {
      await publishBotRelease(record.version_id, force);
      await Promise.all([loadCore(), loadGovernance(), loadOps()]);
      message.success(force ? '版本已强制发布' : '版本已通过门禁并发布');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '发布版本失败'));
    } finally {
      setPublishingVersionId(null);
    }
  };

  const handleRollbackRelease = async (record: BotReleaseVersion) => {
    if (!canConfigure) return;
    setRollingBackVersionId(record.version_id);
    try {
      await rollbackBotRelease(record.version_id);
      await loadGovernance();
      message.success('版本已标记回滚');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '回滚版本失败'));
    } finally {
      setRollingBackVersionId(null);
    }
  };

  const handleCreateFeedback = async () => {
    if (!canEvaluate) return;
    try {
      const values = await feedbackForm.validateFields();
      await createBotFeedback({
        rating: values.rating,
        profile_key: values.profile_key || selectedProfile,
        conversation_id: values.conversation_id?.trim() || conversationId,
        reason: values.reason?.trim(),
        comment: values.comment?.trim(),
      });
      feedbackForm.resetFields(['conversation_id', 'reason', 'comment']);
      feedbackForm.setFieldsValue({ profile_key: selectedProfile, rating: 'wrong' });
      await Promise.all([loadCore(), loadGovernance()]);
      message.success('反馈已进入质量队列');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存反馈失败'));
    }
  };

  const handleSaveCompliancePolicy = async () => {
    if (!canConfigure) return;
    try {
      const values = await complianceForm.validateFields();
      await saveBotCompliancePolicy({
        policy_key: values.policy_key?.trim(),
        name: values.name.trim(),
        policy_type: values.policy_type || 'content_guard',
        status: values.status || 'enabled',
        action: values.action || 'warn',
        rules: {
          blocked_terms: splitTextList(values.blocked_terms_input),
        },
      });
      complianceForm.resetFields(['policy_key', 'name', 'blocked_terms_input']);
      complianceForm.setFieldsValue({ policy_type: 'content_guard', status: 'enabled', action: 'warn' });
      await loadGovernance();
      message.success('合规策略已保存');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存合规策略失败'));
    }
  };

  const profileOptions = profiles.map((item) => ({ value: item.profile_key, label: item.name }));
  const skillOptions = skills.map((item) => ({ value: item.skill_key, label: item.name }));
  const bindingOptions = bindings.map((item) => ({ value: item.channel_key, label: item.channel_name }));

  return (
    <div className="bot-center">
      <WorkbenchPageHeader
        eyebrow="AGENT OPERATIONS"
        title="机器人中心"
        accent="Agent"
        description="机器人接入、Skill 编排、知识检索、对话测试、群发通知和运行审计的统一工作台。"
        actions={[
          { label: '管理配置', icon: <SettingOutlined />, onClick: () => history.push('/management') },
          { label: '新建测试', icon: <RobotOutlined />, onClick: handleNewConversation },
        ]}
      />

      <WorkbenchStatusRail
        items={[
          { label: '机器人 Profile', value: `${overview?.profiles ?? profiles.length} 个`, status: 'good', meta: '身份、边界和 Skill 绑定' },
          { label: '已启用 Skill', value: `${overview?.enabled_skills ?? skills.filter((item) => item.enabled).length} 个`, status: 'good', meta: '受控能力包，不靠 Prompt 硬猜' },
          { label: '知识文件', value: `${overview?.knowledge_files ?? knowledgeTotal} 份`, status: knowledgeTotal ? 'good' : 'warn', meta: '可追溯检索来源' },
          { label: '待审批动作', value: `${overview?.pending_approvals ?? qualitySummary?.pending_actions ?? 0} 个`, status: (overview?.pending_approvals ?? 0) ? 'warn' : 'good', meta: '外部动作先审批再执行' },
          { label: '生产收件箱', value: `${overview?.open_inbox ?? inboxTotal} 个`, status: (overview?.open_inbox ?? inboxTotal) ? 'warn' : 'good', meta: '入站消息、接管和处理闭环' },
          { label: '最近运行', value: overview?.latest_run_at ? formatTime(overview.latest_run_at) : '暂无', status: overview?.latest_run_at ? 'muted' : 'warn', meta: '每次调用都有日志' },
        ]}
      />

      <WorkbenchMetricGrid
        metrics={[
          { label: '当前机器人', value: selectedProfileData?.name || '未选择', icon: <RobotOutlined />, tone: 'blue', hint: selectedProfileData?.description || '选择一个机器人开始测试' },
          { label: '绑定 Skill', value: boundSkills.length, icon: <ToolOutlined />, tone: 'purple', hint: '只调用已绑定且已启用的 Skill' },
          { label: '自动任务', value: overview?.active_tasks ?? taskTotal, icon: <ClockCircleOutlined />, tone: 'green', hint: '按计划或人工触发运行' },
          { label: '评测风险', value: qualitySummary?.failed_evaluation_runs ?? overview?.failed_evaluations ?? 0, icon: <AuditOutlined />, tone: 'gold', hint: '失败用例进入纠错闭环' },
          { label: '渠道适配器', value: overview?.enabled_adapters ?? adapters.filter((item) => item.status === 'enabled').length, icon: <ApiOutlined />, tone: 'blue', hint: '签名、限流、重试和能力声明' },
        ]}
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'chat', label: '对话测试台', forceRender: true, children: renderChatTab() },
          { key: 'skills', label: '配置运营', forceRender: true, children: renderSkillsTab() },
          { key: 'knowledge', label: '知识空间', forceRender: true, children: renderKnowledgeTab() },
          { key: 'channels', label: '生产运营', forceRender: true, children: renderChannelsTab() },
          { key: 'tasks', label: '任务审批', forceRender: true, children: renderTasksTab() },
          { key: 'release', label: '发布观测', forceRender: true, children: renderReleaseTab() },
          { key: 'evaluation', label: '评测纠错', forceRender: true, children: renderEvaluationTab() },
          { key: 'collaboration', label: '协作治理', forceRender: true, children: renderCollaborationTab() },
          { key: 'compliance', label: '合规环境', forceRender: true, children: renderComplianceTab() },
          { key: 'broadcast', label: '消息群发', forceRender: true, children: renderBroadcastTab() },
          { key: 'logs', label: '运行日志', forceRender: true, children: renderLogsTab() },
        ]}
      />
    </div>
  );

  function renderChatTab() {
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

  function renderSkillsTab() {
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

  function renderKnowledgeTab() {
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

  function renderChannelsTab() {
    return (
      <div className="bot-channel-grid">
        <WorkbenchSection title="渠道适配器" description="维护各类群聊入口的认证、签名、限流、重试和能力声明。">
          {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看渠道策略。" />}
          <Form<AdapterFormValues> form={adapterForm} layout="vertical" disabled={!canConfigure}>
            <div className="bot-form-row">
              <Form.Item label="适配器标识" name="adapter_key">
                <Input placeholder="不填则自动生成；已有标识会更新策略" />
              </Form.Item>
              <Form.Item label="适配器名称" name="name" rules={[{ required: true, message: '请输入适配器名称' }]}>
                <Input placeholder="例如：钉钉群聊机器人" />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="渠道类型" name="channel_type" rules={[{ required: true, message: '请选择渠道类型' }]}>
                <Select options={[
                  { value: 'dingtalk', label: '钉钉' },
                  { value: 'feishu', label: '飞书' },
                  { value: 'wecom', label: '企业微信' },
                  { value: 'slack', label: 'Slack' },
                  { value: 'teams', label: 'Teams' },
                  { value: 'webhook', label: 'Webhook' },
                ]} />
              </Form.Item>
              <Form.Item label="状态" name="status">
                <Select options={[{ value: 'enabled', label: '启用' }, { value: 'disabled', label: '停用' }]} />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="事件模式" name="event_mode">
                <Select options={[{ value: 'webhook', label: 'Webhook 回调' }, { value: 'polling', label: '定时拉取' }, { value: 'stream', label: '长连接事件' }]} />
              </Form.Item>
              <Form.Item label="认证方式" name="auth_scheme">
                <Select options={[
                  { value: 'signed_webhook', label: '签名 Webhook' },
                  { value: 'oauth2', label: 'OAuth2' },
                  { value: 'token', label: 'Token' },
                  { value: 'none', label: '无认证' },
                ]} />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="每分钟限流" name="rate_limit_per_minute">
                <InputNumber min={1} max={600} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="signing_required" valuePropName="checked">
                <Switch checkedChildren="校验签名" unCheckedChildren="不校验签名" />
              </Form.Item>
            </div>
            <Form.Item label="能力声明" name="capabilities_input">
              <Input placeholder="用逗号分隔，例如：入站消息,群发消息,文件事件" />
            </Form.Item>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveAdapter}>保存适配器</Button>
          </Form>
        </WorkbenchSection>

        <WorkbenchSection title="群聊绑定" description="把钉钉群、内部测试群或其他外部会话绑定到指定机器人。">
          {!canConfigure && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号只能查看群聊绑定。" />}
          <Form<ChannelFormValues> form={channelForm} layout="vertical" disabled={!canConfigure}>
            <div className="bot-form-row">
              <Form.Item label="群聊标识" name="channel_key">
                <Input placeholder="不填则自动生成；已有标识会更新绑定" />
              </Form.Item>
              <Form.Item label="群聊名称" name="channel_name" rules={[{ required: true, message: '请输入群聊名称' }]}>
                <Input placeholder="例如：市场洞察工作群" />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="渠道类型" name="channel_type">
                <Select options={[{ value: 'dingtalk', label: '钉钉' }, { value: 'test_console', label: '测试入口' }, { value: 'webhook', label: 'Webhook' }]} />
              </Form.Item>
              <Form.Item label="绑定机器人" name="bot_profile_key" rules={[{ required: true, message: '请选择机器人' }]}>
                <Select options={profileOptions} />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="外部会话 ID" name="external_id">
                <Input placeholder="钉钉 openConversationId，可为空" />
              </Form.Item>
              <Form.Item label="状态" name="status">
                <Select options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '停用' }]} />
              </Form.Item>
            </div>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveChannelBinding}>保存群聊绑定</Button>
          </Form>
        </WorkbenchSection>

        <WorkbenchSection title="入站消息测试" description="用真实问法验证群消息路由、Skill 调用和证据链。">
          <Form<InboundFormValues> form={inboundForm} layout="vertical">
            <div className="bot-form-row">
              <Form.Item label="测试群聊" name="channel_key">
                <Select allowClear options={bindingOptions} placeholder="默认使用第一个启用群聊" />
              </Form.Item>
              <Form.Item label="发送人" name="sender_name">
                <Input placeholder={currentUser?.name || '测试用户'} />
              </Form.Item>
            </div>
            <Form.Item label="群聊消息" name="content" rules={[{ required: true, message: '请输入群聊消息' }]}>
              <Input.TextArea rows={4} placeholder="例如：帮我看一下本周公安空间数据相关机会有什么变化" />
            </Form.Item>
            <Button type="primary" icon={<SendOutlined />} onClick={handleInboundTest}>发送入站测试</Button>
          </Form>
          {inboundResult && (
            <div className="bot-preview-answer">
              <strong>机器人回复</strong>
              <p>{inboundResult.assistant_message.content}</p>
              <span>{inboundResult.selected_skills?.length || 0} 个 Skill · {inboundResult.evidence_records?.length || 0} 条证据</span>
            </div>
          )}
        </WorkbenchSection>

        <WorkbenchSection title="人工接管" description="机器人无法闭环或风险较高时，把事项交给负责人处理。">
          {!canApprove && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号没有接管处理权限。" />}
          <Form<HandoffFormValues> form={handoffForm} layout="vertical" disabled={!canApprove}>
            <Form.Item label="收件箱事项" name="inbox_id" rules={[{ required: true, message: '请选择收件箱事项' }]}>
              <Select
                options={inboxItems.map((item) => ({ value: item.inbox_id, label: `${item.priority} · ${item.title}` }))}
                placeholder="选择需要人工接管的事项"
              />
            </Form.Item>
            <div className="bot-form-row">
              <Form.Item label="负责人" name="assignee_name" rules={[{ required: true, message: '请输入负责人' }]}>
                <Input placeholder="例如：张三" />
              </Form.Item>
              <Form.Item label="接管理由" name="reason">
                <Input placeholder="例如：需要销售确认客户状态" />
              </Form.Item>
            </div>
            <Button type="primary" icon={<TeamOutlined />} onClick={handleCreateHandoff}>创建接管</Button>
          </Form>
        </WorkbenchSection>

        <WorkbenchSection title="适配器列表" description="停用的适配器不会作为入站消息处理策略。" className="bot-span-all">
          <Table
            className="edl-table"
            rowKey="adapter_key"
            dataSource={adapters}
            pagination={false}
            scroll={{ x: 1080 }}
            columns={[
              { title: '适配器', dataIndex: 'name', render: (_: string, record: BotChannelAdapter) => <div className="bot-table-title"><strong>{record.name}</strong><span>{record.adapter_key}</span></div> },
              { title: '渠道', dataIndex: 'channel_type', width: 110, render: (value: string) => <Tag color="blue">{value}</Tag> },
              { title: '认证', dataIndex: 'auth_scheme', width: 150 },
              { title: '签名', dataIndex: 'signing_required', width: 90, render: (value: boolean) => value ? <Tag color="success">开启</Tag> : <Tag color="warning">关闭</Tag> },
              { title: '限流', dataIndex: 'rate_limit_per_minute', width: 100, render: (value: number) => `${value}/分钟` },
              { title: '能力', dataIndex: 'capabilities', render: (value: string[]) => (value || []).map((item) => <Tag key={item}>{item}</Tag>) },
              { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'enabled' ? 'success' : 'default'}>{value}</Tag> },
            ]}
          />
        </WorkbenchSection>

        <WorkbenchSection title="绑定列表" description="停用的群聊不会参与真实入站消息路由。" className="bot-span-all">
          <Table
            className="edl-table"
            rowKey="channel_key"
            dataSource={bindings}
            pagination={false}
            scroll={{ x: 980 }}
            columns={[
              { title: '群聊', dataIndex: 'channel_name' },
              { title: '标识', dataIndex: 'channel_key', width: 180 },
              { title: '类型', dataIndex: 'channel_type', width: 120, render: (value: string) => <Tag color="blue">{value}</Tag> },
              { title: '绑定机器人', dataIndex: 'bot_profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
              { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
              { title: '最后消息', dataIndex: 'last_seen_at', width: 170, render: formatTime },
            ]}
          />
        </WorkbenchSection>

        <WorkbenchSection title={`生产收件箱（${inboxTotal}）`} description="入站消息处理后进入这里，便于追踪未闭环事项。" className="bot-span-all">
          <Table
            className="edl-table"
            rowKey="inbox_id"
            dataSource={inboxItems}
            pagination={false}
            scroll={{ x: 1180 }}
            columns={[
              { title: '事项', dataIndex: 'title', render: (_: string, record: BotInboxItem) => <div className="bot-table-title"><strong>{record.title}</strong><span>{record.inbox_id} · {record.sender_name || '外部用户'}</span></div> },
              { title: '优先级', dataIndex: 'priority', width: 90, render: (value: string) => <Tag color={value === 'P0' ? 'error' : value === 'P1' ? 'warning' : 'default'}>{value}</Tag> },
              { title: '渠道', dataIndex: 'channel_name', width: 160 },
              { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'resolved' ? 'success' : value === 'handoff' ? 'warning' : 'processing'}>{value}</Tag> },
              { title: '负责人', dataIndex: 'owner_name', width: 120, render: (value: string) => value || '—' },
              { title: '最后消息', dataIndex: 'last_message_at', width: 170, render: formatTime },
              {
                title: '操作',
                width: 230,
                render: (_: unknown, record: BotInboxItem) => (
                  <Space wrap>
                    <Button size="small" disabled={!canApprove || record.status === 'processing'} onClick={() => handleUpdateInboxStatus(record, 'processing')}>处理中</Button>
                    <Button size="small" disabled={!canApprove || record.status === 'resolved'} onClick={() => handleUpdateInboxStatus(record, 'resolved')}>完成</Button>
                    <Button size="small" disabled={!canApprove} onClick={() => handoffForm.setFieldsValue({ inbox_id: record.inbox_id, assignee_name: currentUser?.name || '' })}>接管</Button>
                  </Space>
                ),
              },
            ]}
          />
        </WorkbenchSection>

        <WorkbenchSection title={`接管记录（${handoffTotal}）`} description="人工接管形成单独记录，便于复盘机器人能力边界。" className="bot-span-all">
          <Table
            className="edl-table"
            rowKey="handoff_id"
            dataSource={handoffs}
            pagination={false}
            scroll={{ x: 980 }}
            columns={[
              { title: '接管编号', dataIndex: 'handoff_id', width: 170 },
              { title: '收件箱', dataIndex: 'inbox_id', width: 170 },
              { title: '负责人', dataIndex: 'assignee_name', width: 130 },
              { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'open' ? 'processing' : 'success'}>{value}</Tag> },
              { title: '理由', dataIndex: 'reason' },
              { title: '申请人', dataIndex: 'requested_by_name', width: 120 },
              { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            ]}
          />
        </WorkbenchSection>
      </div>
    );
  }

  function renderTasksTab() {
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

  function renderReleaseTab() {
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

  function renderEvaluationTab() {
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

  function renderCollaborationTab() {
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

  function renderComplianceTab() {
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

  function renderBroadcastTab() {
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

  function renderLogsTab() {
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
};

const EvidenceList: React.FC<{ evidence: BotEvidenceRecord[] }> = ({ evidence }) => {
  if (!evidence.length) return <Empty description="暂无证据" />;
  return (
    <div className="bot-evidence-list">
      {evidence.slice(0, 8).map((item) => (
        <div className="bot-evidence" key={item.evidence_id}>
          <div>
            <strong>{item.title || item.evidence_id}</strong>
            <Tag>{item.source_type}</Tag>
          </div>
          <p>{item.snippet || item.source || '已命中证据'}</p>
          <span>{item.source || item.category || '内部数据'} {item.published_at ? `· ${item.published_at}` : ''}</span>
        </div>
      ))}
    </div>
  );
};

function formatTime(value?: string | null): string {
  if (!value) return '—';
  return dayjs(value).format('YYYY-MM-DD HH:mm');
}

function splitTextList(value?: string): string[] {
  return String(value || '')
    .split(/[,，;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20);
}

function parseConversationTurns(value?: string): Array<{ role: string; content: string }> {
  return String(value || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(用户|user|机器人|assistant|系统|system)[:：]\s*(.+)$/i);
      if (!match) return { role: 'user', content: line };
      const roleMap: Record<string, string> = {
        用户: 'user',
        user: 'user',
        机器人: 'assistant',
        assistant: 'assistant',
        系统: 'system',
        system: 'system',
      };
      return { role: roleMap[match[1]] || 'user', content: match[2].trim() };
    })
    .filter((item) => item.content)
    .slice(0, 12);
}

export default BotCenter;
