import { message } from 'antd';
import {
  BotKnowledgeFile,
  BotKnowledgeSyncJob,
  createBotKnowledgeSyncJob,
  createBotKnowledgeText,
  getApiErrorMessage,
  runBotKnowledgeSyncJob,
  searchBotKnowledge,
  updateBotKnowledgeFile,
  uploadBotKnowledgeFile,
} from '@/services/api';
import { DEFAULT_KNOWLEDGE_FORM, splitTextList } from './botCenterShared';
import { BotCenterActionContext } from './botCenterControllerTypes';

export function useBotCenterKnowledgeActions(ctx: BotCenterActionContext) {
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

  return { handleUpdateKnowledgeStatus, handleCreateKnowledge, handleUploadKnowledge, handleSearchKnowledge, handleCreateSyncJob, handleRunSyncJob };
}
