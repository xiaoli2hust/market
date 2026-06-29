import { useState } from 'react';
import { Form } from 'antd';
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
  getCurrentUser,
  userHasPermission,
} from '@/services/api';
import {
  AdapterFormValues,
  ApprovalFormValues,
  BroadcastFormValues,
  ChannelFormValues,
  CollaborationFormValues,
  ComplianceFormValues,
  CorrectionFormValues,
  FeedbackFormValues,
  HandoffFormValues,
  InboundFormValues,
  KnowledgeFormValues,
  KnowledgeSyncFormValues,
  ProfileFormValues,
  ReleaseFormValues,
  TaskFormValues,
  TestCaseFormValues,
} from './botCenterShared';

export function useBotCenterState() {
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

  return {
    currentUser,
    canConfigure,
    canManageKnowledge,
    canApprove,
    canEvaluate,
    canBroadcast,
    activeTab,
    setActiveTab,
    loading,
    setLoading,
    overview,
    setOverview,
    profiles,
    setProfiles,
    skills,
    setSkills,
    selectedProfile,
    setSelectedProfile,
    chatInput,
    setChatInput,
    simulatedRole,
    setSimulatedRole,
    conversationId,
    setConversationId,
    chatMessages,
    setChatMessages,
    chatResult,
    setChatResult,
    chatSending,
    setChatSending,
    broadcastForm,
    broadcasts,
    setBroadcasts,
    broadcastTotal,
    setBroadcastTotal,
    broadcastStatusFilter,
    setBroadcastStatusFilter,
    broadcastSaving,
    setBroadcastSaving,
    broadcastSending,
    setBroadcastSending,
    resendingId,
    setResendingId,
    knowledgeForm,
    knowledgeFiles,
    setKnowledgeFiles,
    knowledgeTotal,
    setKnowledgeTotal,
    knowledgeFile,
    setKnowledgeFile,
    knowledgeUploading,
    setKnowledgeUploading,
    knowledgeQuery,
    setKnowledgeQuery,
    knowledgeSearchResult,
    setKnowledgeSearchResult,
    profileForm,
    channelForm,
    adapterForm,
    inboundForm,
    handoffForm,
    taskForm,
    approvalForm,
    testCaseForm,
    correctionForm,
    collaborationForm,
    releaseForm,
    feedbackForm,
    syncForm,
    complianceForm,
    bindings,
    setBindings,
    adapters,
    setAdapters,
    inboxItems,
    setInboxItems,
    inboxTotal,
    setInboxTotal,
    handoffs,
    setHandoffs,
    handoffTotal,
    setHandoffTotal,
    skillRuns,
    setSkillRuns,
    auditLogs,
    setAuditLogs,
    inboundResult,
    setInboundResult,
    tasks,
    setTasks,
    taskTotal,
    setTaskTotal,
    taskRuns,
    setTaskRuns,
    taskRunningId,
    setTaskRunningId,
    approvals,
    setApprovals,
    approvalTotal,
    setApprovalTotal,
    testCases,
    setTestCases,
    evaluationRuns,
    setEvaluationRuns,
    intentCorrections,
    setIntentCorrections,
    caseRunningId,
    setCaseRunningId,
    collaborations,
    setCollaborations,
    collaborationRunning,
    setCollaborationRunning,
    qualitySummary,
    setQualitySummary,
    releases,
    setReleases,
    releaseTotal,
    setReleaseTotal,
    publishingVersionId,
    setPublishingVersionId,
    rollingBackVersionId,
    setRollingBackVersionId,
    feedbackItems,
    setFeedbackItems,
    feedbackTotal,
    setFeedbackTotal,
    syncJobs,
    setSyncJobs,
    syncRunningId,
    setSyncRunningId,
    environments,
    setEnvironments,
    compliancePolicies,
    setCompliancePolicies,
    observability,
    setObservability,
  };
}

export type BotCenterState = ReturnType<typeof useBotCenterState>;
