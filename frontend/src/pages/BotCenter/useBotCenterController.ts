import { useEffect, useMemo } from 'react';
import { useBotCenterBroadcastActions } from './useBotCenterBroadcastActions';
import { useBotCenterCoreActions } from './useBotCenterCoreActions';
import { useBotCenterKnowledgeActions } from './useBotCenterKnowledgeActions';
import { useBotCenterLoaders } from './useBotCenterLoaders';
import { useBotCenterReleaseActions } from './useBotCenterReleaseActions';
import { useBotCenterState } from './useBotCenterState';
import { buildBotCenterViewContext } from './botCenterViewContextBuilder';

export function useBotCenterController() {
  const state = useBotCenterState();
  const loaders = useBotCenterLoaders(state);
  const {
    adapterForm,
    approvalForm,
    channelForm,
    collaborationForm,
    complianceForm,
    correctionForm,
    currentUser,
    feedbackForm,
    handoffForm,
    profileForm,
    profiles,
    releaseForm,
    selectedProfile,
    skills,
    syncForm,
    taskForm,
    testCaseForm,
    adapters,
    bindings,
    knowledgeTotal,
    overview,
    qualitySummary,
    inboxTotal,
    taskTotal,
  } = state;
  const { loadBroadcasts, loadCore, loadGovernance, loadKnowledge, loadOps } = loaders;

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


  const profileOptions = profiles.map((item) => ({ value: item.profile_key, label: item.name }));
  const skillOptions = skills.map((item) => ({ value: item.skill_key, label: item.name }));
  const bindingOptions = bindings.map((item) => ({ value: item.channel_key, label: item.channel_name }));
  const derived = { selectedProfileData, boundSkills, profileOptions, skillOptions, bindingOptions };
  const actionContext = { ...state, ...loaders, ...derived };
  const coreActions = useBotCenterCoreActions(actionContext);
  const broadcastActions = useBotCenterBroadcastActions(actionContext);
  const knowledgeActions = useBotCenterKnowledgeActions(actionContext);
  const releaseActions = useBotCenterReleaseActions(actionContext);
  const actions = { ...coreActions, ...broadcastActions, ...knowledgeActions, ...releaseActions };
  const botCenterViewContext = buildBotCenterViewContext({ ...actionContext, ...actions });

  return {
    ...state,
    ...loaders,
    ...derived,
    ...actions,
    botCenterViewContext,
    adapters,
    knowledgeTotal,
    overview,
    qualitySummary,
    inboxTotal,
    taskTotal,
  };
}
