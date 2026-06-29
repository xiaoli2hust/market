import { useCallback } from 'react';
import { message } from 'antd';
import {
  fetchBotApprovals,
  fetchBotAuditLogs,
  fetchBotBroadcasts,
  fetchBotChannelAdapters,
  fetchBotChannelBindings,
  fetchBotCollaborations,
  fetchBotCompliancePolicies,
  fetchBotEnvironments,
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
} from '@/services/api';
import { PAGE_SIZE } from './botCenterShared';
import { BotCenterState } from './useBotCenterState';

export function useBotCenterLoaders(state: BotCenterState) {
  const {
    setLoading,
    setOverview,
    setProfiles,
    setSkills,
    selectedProfile,
    setSelectedProfile,
    broadcastStatusFilter,
    setBroadcasts,
    setBroadcastTotal,
    setKnowledgeFiles,
    setKnowledgeTotal,
    setBindings,
    setSkillRuns,
    setAuditLogs,
    setAdapters,
    setInboxItems,
    setInboxTotal,
    setHandoffs,
    setHandoffTotal,
    setTasks,
    setTaskTotal,
    setApprovals,
    setApprovalTotal,
    setTestCases,
    setEvaluationRuns,
    setIntentCorrections,
    setCollaborations,
    setQualitySummary,
    setTaskRuns,
    setReleases,
    setReleaseTotal,
    setFeedbackItems,
    setFeedbackTotal,
    setSyncJobs,
    setEnvironments,
    setCompliancePolicies,
    setObservability,
  } = state;

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

  return { loadCore, loadBroadcasts, loadKnowledge, loadOps, loadGovernance };
}

export type BotCenterLoaders = ReturnType<typeof useBotCenterLoaders>;
