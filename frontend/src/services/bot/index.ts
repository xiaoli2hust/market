import { request } from '@@/exports';
import { LONG_TASK_TIMEOUT_MS } from '../common';
import type {
  BotBroadcastStatus,
  BotMessageType,
  BotOverview,
  BotProfile,
  BotSkill,
  BotConversation,
  BotMessage,
  BotEvidenceRecord,
  BotToolCall,
  BotSkillRun,
  BotChatTestResult,
  BotKnowledgeFile,
  BotChannelBinding,
  BotChannelAdapter,
  BotInboxItem,
  BotHandoff,
  BotAuditLog,
  BotBroadcastItem,
  BotBroadcastPayload,
  BotTask,
  BotTaskRun,
  BotActionApproval,
  BotTestCase,
  BotEvaluationRun,
  BotIntentCorrection,
  BotCollaborationRun,
  BotQualitySummary,
  BotReleaseVersion,
  BotFeedback,
  BotKnowledgeSyncJob,
  BotEnvironment,
  BotCompliancePolicy,
  BotObservabilitySummary
} from './types';

export * from './types';

export async function fetchBotOverview() {
  return request<BotOverview>('/api/bot/overview', { method: 'GET' });
}

export async function fetchBotProfiles() {
  return request<BotProfile[]>('/api/bot/profiles', { method: 'GET' });
}

export async function createBotProfile(data: Partial<BotProfile>) {
  return request<BotProfile>('/api/bot/profiles', { method: 'POST', data });
}

export async function updateBotProfile(profileKey: string, data: Partial<BotProfile>) {
  return request<BotProfile>(`/api/bot/profiles/${profileKey}`, { method: 'PUT', data });
}

export async function fetchBotSkills(params?: { category?: string }) {
  return request<BotSkill[]>('/api/bot/skills', { method: 'GET', params });
}

export async function updateBotSkill(skillKey: string, data: {
  enabled?: boolean;
  config?: Record<string, any>;
  trigger_scenarios?: string[];
  evidence_rules?: Record<string, any>;
  input_contract?: Record<string, any>;
  output_contract?: Record<string, any>;
}) {
  return request<BotSkill>(`/api/bot/skills/${skillKey}`, { method: 'PUT', data });
}

export async function runBotChatTest(data: {
  profile_key: string;
  message: string;
  conversation_id?: string;
  simulated_user_role?: string;
}) {
  return request<BotChatTestResult>('/api/bot/chat/test', {
    method: 'POST',
    data,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function fetchBotConversations(params?: {
  profile_key?: string;
  page?: number;
  page_size?: number;
}) {
  return request<{ total: number; items: BotConversation[] }>('/api/bot/conversations', { method: 'GET', params });
}

export async function fetchBotConversationDetail(conversationId: string) {
  return request<{
    conversation: BotConversation;
    messages: BotMessage[];
    skill_runs: BotSkillRun[];
  }>(`/api/bot/conversations/${conversationId}`, { method: 'GET' });
}

export async function fetchBotKnowledgeFiles(params?: {
  category?: string;
  page?: number;
  page_size?: number;
}) {
  return request<{ total: number; items: BotKnowledgeFile[] }>('/api/bot/knowledge/files', { method: 'GET', params });
}

export async function createBotKnowledgeText(data: {
  title: string;
  category?: string;
  text_content: string;
  owner_profile_key?: string;
  visibility_scope?: string;
  review_status?: string;
  tags?: string[];
}) {
  return request<BotKnowledgeFile>('/api/bot/knowledge/text', { method: 'POST', data });
}

export async function uploadBotKnowledgeFile(data: {
  title: string;
  category?: string;
  file: File;
}) {
  const form = new FormData();
  form.append('title', data.title);
  form.append('category', data.category || 'general');
  form.append('file', data.file);
  const resp = await fetch('/api/bot/knowledge/upload', {
    method: 'POST',
    credentials: 'same-origin',
    body: form,
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw Object.assign(new Error(body?.detail || body?.message || '知识文件上传失败'), { data: body });
  }
  return body as BotKnowledgeFile;
}

export async function searchBotKnowledge(query: string) {
  return request<{ query: string; evidence_records: BotEvidenceRecord[]; conversation: BotConversation }>(
    '/api/bot/knowledge/search',
    { method: 'POST', data: { query }, timeout: LONG_TASK_TIMEOUT_MS },
  );
}

export async function updateBotKnowledgeFile(fileId: string, data: Partial<BotKnowledgeFile>) {
  return request<BotKnowledgeFile>(`/api/bot/knowledge/files/${fileId}`, { method: 'PUT', data });
}

export async function fetchBotChannelBindings() {
  return request<BotChannelBinding[]>('/api/bot/channel-bindings', { method: 'GET' });
}

export async function createBotChannelBinding(data: Partial<BotChannelBinding>) {
  return request<BotChannelBinding>('/api/bot/channel-bindings', { method: 'POST', data });
}

export async function updateBotChannelBinding(channelKey: string, data: Partial<BotChannelBinding>) {
  return request<BotChannelBinding>(`/api/bot/channel-bindings/${channelKey}`, { method: 'PUT', data });
}

export async function fetchBotChannelAdapters() {
  return request<BotChannelAdapter[]>('/api/bot/channel-adapters', { method: 'GET' });
}

export async function saveBotChannelAdapter(data: Partial<BotChannelAdapter>) {
  return request<BotChannelAdapter>('/api/bot/channel-adapters', { method: 'POST', data });
}

export async function runBotInboundTest(data: {
  channel_key?: string;
  content: string;
  sender_id?: string;
  sender_name?: string;
}) {
  return request<BotChatTestResult>('/api/bot/inbound/test', {
    method: 'POST',
    data,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function fetchBotInbox(params?: { status?: string }) {
  return request<{ total: number; items: BotInboxItem[] }>('/api/bot/inbox', { method: 'GET', params });
}

export async function updateBotInboxItem(inboxId: string, data: Partial<BotInboxItem>) {
  return request<BotInboxItem>(`/api/bot/inbox/${inboxId}`, { method: 'PUT', data });
}

export async function createBotHandoff(inboxId: string, data: { assignee_name: string; reason?: string }) {
  return request<BotHandoff>(`/api/bot/inbox/${inboxId}/handoff`, { method: 'POST', data });
}

export async function fetchBotHandoffs(params?: { status?: string }) {
  return request<{ total: number; items: BotHandoff[] }>('/api/bot/handoffs', { method: 'GET', params });
}

export async function fetchBotSkillRuns(params?: {
  skill_key?: string;
  page?: number;
  page_size?: number;
}) {
  return request<{ total: number; items: BotSkillRun[] }>('/api/bot/skill-runs', { method: 'GET', params });
}

export async function fetchBotAuditLogs(params?: { page?: number; page_size?: number }) {
  return request<{ total: number; items: BotAuditLog[] }>('/api/bot/audit-logs', { method: 'GET', params });
}

export async function fetchBotTasks(params?: { page?: number; page_size?: number }) {
  return request<{ total: number; items: BotTask[] }>('/api/bot/tasks', { method: 'GET', params });
}

export async function createBotTask(data: Partial<BotTask>) {
  return request<BotTask>('/api/bot/tasks', { method: 'POST', data });
}

export async function runBotTask(taskId: string) {
  return request<BotTask>(`/api/bot/tasks/${taskId}/run`, { method: 'POST', timeout: LONG_TASK_TIMEOUT_MS });
}

export async function fetchBotTaskRuns(params?: { task_id?: string }) {
  return request<{ total: number; items: BotTaskRun[] }>('/api/bot/task-runs', { method: 'GET', params });
}

export async function fetchBotApprovals(params?: { status?: string; page?: number; page_size?: number }) {
  return request<{ total: number; items: BotActionApproval[] }>('/api/bot/approvals', { method: 'GET', params });
}

export async function createBotApproval(data: Partial<BotActionApproval>) {
  return request<BotActionApproval>('/api/bot/approvals', { method: 'POST', data });
}

export async function decideBotApproval(actionId: string, decision: 'approve' | 'reject' | 'execute') {
  return request<BotActionApproval>(`/api/bot/approvals/${actionId}/${decision}`, { method: 'POST' });
}

export async function fetchBotTestCases(params?: { profile_key?: string; page?: number; page_size?: number }) {
  return request<{ total: number; items: BotTestCase[] }>('/api/bot/test-cases', { method: 'GET', params });
}

export async function createBotTestCase(data: Partial<BotTestCase>) {
  return request<BotTestCase>('/api/bot/test-cases', { method: 'POST', data });
}

export async function runBotTestCase(caseId: number) {
  return request<{ test_case: BotTestCase; run: BotEvaluationRun }>(
    `/api/bot/test-cases/${caseId}/run`,
    { method: 'POST', timeout: LONG_TASK_TIMEOUT_MS },
  );
}

export async function fetchBotEvaluationRuns(params?: { page?: number; page_size?: number }) {
  return request<{ total: number; items: BotEvaluationRun[] }>('/api/bot/evaluation-runs', { method: 'GET', params });
}

export async function fetchBotIntentCorrections() {
  return request<BotIntentCorrection[]>('/api/bot/intent-corrections', { method: 'GET' });
}

export async function createBotIntentCorrection(data: Partial<BotIntentCorrection>) {
  return request<BotIntentCorrection>('/api/bot/intent-corrections', { method: 'POST', data });
}

export async function fetchBotCollaborations(params?: { page?: number; page_size?: number }) {
  return request<{ total: number; items: BotCollaborationRun[] }>('/api/bot/collaborations', { method: 'GET', params });
}

export async function runBotCollaboration(data: Partial<BotCollaborationRun>) {
  return request<BotCollaborationRun>('/api/bot/collaborations/run', {
    method: 'POST',
    data,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function fetchBotQualitySummary() {
  return request<BotQualitySummary>('/api/bot/quality-summary', { method: 'GET' });
}

export async function fetchBotReleases(params?: { profile_key?: string }) {
  return request<{ total: number; items: BotReleaseVersion[] }>('/api/bot/releases', { method: 'GET', params });
}

export async function createBotRelease(data: { profile_key: string; environment_key?: string; change_note?: string }) {
  return request<BotReleaseVersion>('/api/bot/releases', { method: 'POST', data });
}

export async function publishBotRelease(versionId: string, force = false) {
  return request<BotReleaseVersion>(`/api/bot/releases/${versionId}/publish`, {
    method: 'POST',
    params: { force },
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function rollbackBotRelease(versionId: string) {
  return request<BotReleaseVersion>(`/api/bot/releases/${versionId}/rollback`, { method: 'POST' });
}

export async function fetchBotFeedback(params?: { status?: string }) {
  return request<{ total: number; items: BotFeedback[] }>('/api/bot/feedback', { method: 'GET', params });
}

export async function createBotFeedback(data: Partial<BotFeedback>) {
  return request<BotFeedback>('/api/bot/feedback', { method: 'POST', data });
}

export async function fetchBotKnowledgeSyncJobs() {
  return request<{ total: number; items: BotKnowledgeSyncJob[] }>('/api/bot/knowledge-sync', { method: 'GET' });
}

export async function createBotKnowledgeSyncJob(data: Partial<BotKnowledgeSyncJob>) {
  return request<BotKnowledgeSyncJob>('/api/bot/knowledge-sync', { method: 'POST', data });
}

export async function runBotKnowledgeSyncJob(jobId: string) {
  return request<BotKnowledgeSyncJob>(`/api/bot/knowledge-sync/${jobId}/run`, {
    method: 'POST',
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function fetchBotEnvironments() {
  return request<BotEnvironment[]>('/api/bot/environments', { method: 'GET' });
}

export async function fetchBotCompliancePolicies() {
  return request<BotCompliancePolicy[]>('/api/bot/compliance-policies', { method: 'GET' });
}

export async function saveBotCompliancePolicy(data: Partial<BotCompliancePolicy>) {
  return request<BotCompliancePolicy>('/api/bot/compliance-policies', { method: 'POST', data });
}

export async function fetchBotObservabilitySummary() {
  return request<BotObservabilitySummary>('/api/bot/observability-summary', { method: 'GET' });
}

export async function fetchBotBroadcasts(params?: {
  status?: BotBroadcastStatus;
  page?: number;
  page_size?: number;
}) {
  return request<{ total: number; items: BotBroadcastItem[] }>('/api/bot/broadcasts', {
    method: 'GET',
    params,
  });
}

export async function createBotBroadcast(data: BotBroadcastPayload) {
  return request<BotBroadcastItem>('/api/bot/broadcasts', {
    method: 'POST',
    data,
  });
}

export async function sendBotBroadcast(data: BotBroadcastPayload) {
  return request<BotBroadcastItem>('/api/bot/broadcasts/send', {
    method: 'POST',
    data,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function sendExistingBotBroadcast(id: number) {
  return request<BotBroadcastItem>(`/api/bot/broadcasts/${id}/send`, {
    method: 'POST',
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}
