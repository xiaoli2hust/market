import { request } from '@@/exports';
import { LONG_TASK_TIMEOUT_MS } from './common';

export interface CrawlerSourceItem {
  id: number;
  category: string;
  name: string;
  url: string;
  base_url?: string;
  selectors?: Record<string, any>;
  risk_level?: string;
  crawl_policy?: Record<string, any>;
  anti_crawl_strategy?: string;
  source_tier?: {
    code: string;
    label: string;
    rank: number;
    description: string;
  };
  strategy_status?: string;
  strategy_status_label?: string;
  strategy_gaps?: string[];
  strategy_sort_rank?: number;
  collection_strategy?: string;
  anti_crawl_plan?: string;
  strategy_steps?: string[];
  stop_rules?: string[];
  operator_action?: string;
  rule_profile?: string;
  rule_status?: string;
  rule_note?: string;
  is_active: boolean;
  capability_status?: string;
  capability_reason?: string;
  runtime_status?: string;
  runtime_reason?: string;
  consecutive_failures?: number;
  cooldown_until?: string | null;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_diagnosis_code?: string | null;
  last_diagnosis_label?: string | null;
  last_error_message?: string | null;
  last_cursor?: Record<string, any> | null;
  last_found?: number;
  last_saved?: number;
  created_at: string;
}

export interface KeywordCategory {
  category: string;
  keywords: string[];
}

export async function fetchCrawlerSources(category?: string): Promise<CrawlerSourceItem[]> {
  return request<CrawlerSourceItem[]>('/api/crawler-config/sources', {
    method: 'GET',
    params: category ? { category } : {},
  });
}

export async function createCrawlerSource(data: Partial<CrawlerSourceItem>) {
  return request('/api/crawler-config/sources', { method: 'POST', data });
}

export async function updateCrawlerSource(id: number, data: Partial<CrawlerSourceItem>) {
  return request(`/api/crawler-config/sources/${id}`, { method: 'PUT', data });
}

export async function deleteCrawlerSource(id: number) {
  return request(`/api/crawler-config/sources/${id}`, { method: 'DELETE' });
}

export async function fetchKeywords(): Promise<KeywordCategory[]> {
  return request<KeywordCategory[]>('/api/crawler-config/keywords', { method: 'GET' });
}

export async function updateKeywords(category: string, keywords: string[]) {
  return request('/api/crawler-config/keywords', { method: 'PUT', data: { category, keywords } });
}

export async function fetchSchedule() {
  return request('/api/crawler-config/schedule', { method: 'GET' });
}

export async function updateSchedule(data: Record<string, any>) {
  return request('/api/crawler-config/schedule', { method: 'PUT', data });
}

/* ---------- 管理中心：大模型 ---------- */

export interface LLMConfigData {
  model_name: string;
  api_base_url: string;
  api_key_masked: string;
  default_temperature: number;
  configured: boolean;
}

export interface PromptTemplate {
  scene: string;
  name: string;
  template: string;
  temperature: number;
  max_tokens: number;
}

export async function fetchLLMConfig(): Promise<LLMConfigData> {
  return request<LLMConfigData>('/api/llm/config', { method: 'GET' });
}

export async function updateLLMConfig(data: Record<string, any>) {
  return request('/api/llm/config', { method: 'PUT', data });
}

export async function testLLMConnection() {
  return request('/api/llm/test', { method: 'POST' });
}

export async function fetchPrompts(): Promise<PromptTemplate[]> {
  return request<PromptTemplate[]>('/api/llm/prompts', { method: 'GET' });
}

export async function updatePrompt(scene: string, data: Partial<PromptTemplate>) {
  return request(`/api/llm/prompts/${scene}`, { method: 'PUT', data });
}

export interface LLMStats {
  implemented: boolean;
  message?: string;
  today_calls: number;
  todayTokens: number;
  todayAvgLatencyMs?: number;
  todayErrors?: number;
  weekCalls: number;
  weekTokens: number;
  weekAvgLatencyMs?: number;
  weekErrors?: number;
  byScene: Record<string, { calls: number; tokens: number; errors?: number }>;
  recentErrors?: Array<{
    scene: string;
    model_name?: string | null;
    error_message?: string | null;
    created_at?: string | null;
  }>;
}

export async function fetchLLMStats(): Promise<LLMStats> {
  return request<LLMStats>('/api/llm/stats', { method: 'GET' });
}

/* ---------- 管理中心：用户管理 ---------- */

export interface SystemUser {
  id: number;
  username: string;
  role: string;
  role_label: string;
  display_name: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface RoleDef {
  key: string;
  label: string;
  permissions: string[];
}

export async function fetchSystemUsers(page = 1, pageSize = 20) {
  return request<{ total: number; items: SystemUser[] }>('/api/system-users/', {
    method: 'GET',
    params: { page, page_size: pageSize },
  });
}

export async function createSystemUser(data: { username: string; password: string; role: string; display_name?: string }) {
  return request('/api/system-users/', { method: 'POST', data });
}

export async function updateSystemUser(id: number, data: Record<string, any>) {
  return request(`/api/system-users/${id}`, { method: 'PUT', data });
}

export async function resetUserPassword(id: number, password: string) {
  return request(`/api/system-users/${id}/reset-password`, { method: 'POST', data: { password } });
}

export async function deleteSystemUser(id: number) {
  return request(`/api/system-users/${id}`, { method: 'DELETE' });
}

export async function fetchRoles(): Promise<RoleDef[]> {
  return request<RoleDef[]>('/api/system-users/roles', { method: 'GET' });
}

export async function fetchOperationLogs(page = 1, pageSize = 20) {
  return request<{ total: number; items: any[] }>('/api/system-users/logs', {
    method: 'GET',
    params: { page, page_size: pageSize },
  });
}

/* ---------- 管理中心：系统设置 ---------- */

export interface APIKeyItem {
  id: number;
  name: string;
  purpose: string;
  key_masked: string;
  is_active: boolean;
  created_at: string;
}

export async function fetchAPIKeys(): Promise<APIKeyItem[]> {
  return request<APIKeyItem[]>('/api/settings/api-keys', { method: 'GET' });
}

export async function createAPIKey(data: { name: string; purpose: string }) {
  return request('/api/settings/api-keys', { method: 'POST', data });
}

export async function deleteAPIKey(id: number) {
  return request(`/api/settings/api-keys/${id}`, { method: 'DELETE' });
}

export async function toggleAPIKey(id: number) {
  return request(`/api/settings/api-keys/${id}/toggle`, { method: 'PUT' });
}

export async function fetchDingtalkConfig() {
  return request('/api/settings/dingtalk', { method: 'GET' });
}

export async function updateDingtalkConfig(data: {
  delivery_mode?: 'webhook' | 'openapi';
  webhook_url?: string;
  secret?: string;
  app_key?: string;
  app_secret?: string;
  app_id?: string;
  agent_id?: string;
  robot_code?: string;
  open_conversation_id?: string;
  cool_app_code?: string;
  jianyu_username?: string;
  jianyu_password?: string;
  jianyu_api_key?: string;
}) {
  return request('/api/settings/dingtalk', { method: 'PUT', data });
}

export async function testDingtalk() {
  return request('/api/settings/dingtalk/test', { method: 'POST' });
}

export interface AipaasUserItem {
  user_id: string;
  user_name: string;
}

export interface AipaasConfigData {
  base_url: string;
  app_id: string;
  sync_enabled: boolean;
  sync_interval_minutes: number;
  sync_users: AipaasUserItem[];
  last_sync_at?: string | null;
  last_sync_result?: Record<string, any> | null;
  source?: string;
  configured?: boolean;
}

export async function fetchAipaasConfig(): Promise<AipaasConfigData> {
  return request<AipaasConfigData>('/api/aipaas-sync/config', { method: 'GET' });
}

export async function updateAipaasConfig(data: Partial<AipaasConfigData>) {
  return request<AipaasConfigData>('/api/aipaas-sync/config', { method: 'PUT', data });
}

export async function triggerAipaasSync(data: { date?: string; users?: AipaasUserItem[] } = {}) {
  return request('/api/aipaas-sync/trigger', {
    method: 'POST',
    data,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function fetchSystemInfo() {
  return request('/api/settings/system', { method: 'GET' });
}
