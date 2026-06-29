import { message } from 'antd';
import {
  BotActionApproval,
  BotInboxItem,
  BotSkill,
  BotTask,
  BotTestCase,
  createBotApproval,
  createBotChannelBinding,
  createBotHandoff,
  createBotIntentCorrection,
  createBotProfile,
  createBotTask,
  createBotTestCase,
  decideBotApproval,
  getApiErrorMessage,
  runBotChatTest,
  runBotCollaboration,
  runBotInboundTest,
  runBotTask,
  runBotTestCase,
  saveBotChannelAdapter,
  updateBotChannelBinding,
  updateBotInboxItem,
  updateBotProfile,
  updateBotSkill,
} from '@/services/api';
import { parseConversationTurns, splitTextList } from './botCenterShared';
import { BotCenterActionContext } from './botCenterControllerTypes';

export function useBotCenterCoreActions(ctx: BotCenterActionContext) {
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

  return {
    handleChatSend,
    handleNewConversation,
    handleToggleSkill,
    handleSaveProfile,
    handleSaveChannelBinding,
    handleSaveAdapter,
    handleInboundTest,
    handleUpdateInboxStatus,
    handleCreateHandoff,
    handleCreateTask,
    handleRunTask,
    handleCreateApproval,
    handleDecideApproval,
    handleCreateTestCase,
    handleRunCase,
    handleCreateCorrection,
    handleRunCollaboration,
  };
}
