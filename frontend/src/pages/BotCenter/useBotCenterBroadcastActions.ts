import { message } from 'antd';
import {
  BotBroadcastItem,
  BotBroadcastPayload,
  createBotBroadcast,
  getApiErrorMessage,
  sendBotBroadcast,
  sendExistingBotBroadcast,
} from '@/services/api';
import { DEFAULT_BROADCAST_FORM } from './botCenterShared';
import { BotCenterActionContext } from './botCenterControllerTypes';

export function useBotCenterBroadcastActions(ctx: BotCenterActionContext) {
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

  return { handleSaveDraft, handleSendNow, handleResend };
}
