import { message } from 'antd';
import {
  BotReleaseVersion,
  createBotFeedback,
  createBotRelease,
  getApiErrorMessage,
  publishBotRelease,
  rollbackBotRelease,
  saveBotCompliancePolicy,
} from '@/services/api';
import { splitTextList } from './botCenterShared';
import { BotCenterActionContext } from './botCenterControllerTypes';

export function useBotCenterReleaseActions(ctx: BotCenterActionContext) {
  const {
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
    loadCore,
    loadBroadcasts,
    loadKnowledge,
    loadOps,
    loadGovernance,
    selectedProfileData,
    boundSkills,
    profileOptions,
    skillOptions,
    bindingOptions,
  } = ctx;

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

  return { handleCreateRelease, handlePublishRelease, handleRollbackRelease, handleCreateFeedback, handleSaveCompliancePolicy };
}
