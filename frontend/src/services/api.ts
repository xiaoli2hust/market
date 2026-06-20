import { request } from '@umijs/max';

/* ---------- 类型 ---------- */
export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user?: { id: number; name: string; role?: string; department?: string };
}

export interface Staff {
  id: number;
  name: string;
  role?: string;
  department?: string;
}

export interface ActivityItem {
  id: number;
  user_id: number;
  user_name: string;
  user_department?: string;
  action_type: string;
  action_type_label: string;
  summary: string;
  detail?: string;
  description?: string;
  customer_name?: string;
  opportunity_id?: number | null;
  opportunity_name?: string | null;
  activity_date: string;
  source?: string;
}

export interface ActivityListParams {
  start_date?: string;
  end_date?: string;
  user_id?: number;
  action_type?: string;
  department?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export interface DashboardStats {
  total_activities: number;
  today_activities: number;
  total_users: number;
  total_opportunities: number;
  action_type_breakdown: Record<string, number>;
  department_breakdown: Record<string, number>;
  recent_activities: ActivityItem[];
  daily_trend: { date: string; count: number }[];
}

export interface StaffDetail {
  staff: Staff;
  active_days: number;
  visit_count: number;
  opportunity_count: number;
  recent_activities: ActivityItem[];
}

/* ---------- 鉴权 ---------- */
const TOKEN_KEY = 'market_token';
const USER_KEY = 'market_user';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user?: LoginResult['user']) {
  localStorage.setItem(TOKEN_KEY, token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getCurrentUser(): LoginResult['user'] | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/* ---------- 请求 ---------- */

/**
 * 登录。直接用 fetch 调用后端，避免 umi-request 的响应包装问题。
 */
export async function login(payload: LoginPayload): Promise<LoginResult> {
  if (!payload.username || !payload.password) {
    throw new Error('用户名或密码不能为空');
  }

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody?.detail || `登录失败 (${resp.status})`);
    }

    const data = await resp.json();
    const token = data?.token || data?.access_token;
    if (!token) {
      throw new Error('登录响应中未包含 token');
    }

    return {
      token,
      user: data?.user || { id: 0, name: payload.username, role: 'admin', department: '总部' },
    };
  } catch (err: any) {
    if (err?.message?.includes('Failed to fetch') || err?.message?.includes('NetworkError')) {
      throw new Error('无法连接到后端服务，请确认后端已启动');
    }
    throw err;
  }
}

/**
 * 拉取活动列表。
 * 后端使用 skip/limit；前端按 page/page_size 调用，自动转换。
 */
export async function fetchActivities(
  params: ActivityListParams,
): Promise<{ list: ActivityItem[]; total: number }> {
  const page = params.page ?? 1;
  const pageSize = params.page_size ?? 20;
  const query: Record<string, any> = {
    skip: (page - 1) * pageSize,
    limit: pageSize,
    start_date: params.start_date,
    end_date: params.end_date,
    user_id: params.user_id,
    action_type: params.action_type,
    department: params.department,
  };
  Object.keys(query).forEach((k) => query[k] === undefined && delete query[k]);

  const resp = await request<{ items?: ActivityItem[]; list?: ActivityItem[] } | ActivityItem[]>('/api/activities/', {
    method: 'GET',
    params: query,
  });

  // 兼容后端分页包装格式 {items: [...]} 和纯数组格式
  let list: ActivityItem[];
  if (Array.isArray(resp)) {
    list = resp;
  } else {
    list = resp?.items || resp?.list || [];
  }

  let filtered = list || [];
  if (params.keyword) {
    const kw = params.keyword.toLowerCase();
    filtered = filtered.filter(
      (a) =>
        a.summary?.toLowerCase().includes(kw) ||
        a.customer_name?.toLowerCase().includes(kw) ||
        a.user_name?.toLowerCase().includes(kw) ||
        a.action_type_label?.toLowerCase().includes(kw),
    );
  }
  return { list: filtered, total: filtered.length + (filtered.length === pageSize ? pageSize : 0) };
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return request<DashboardStats>('/api/activities/dashboard', { method: 'GET' });
}

export async function fetchStaff(department?: string): Promise<Staff[]> {
  const list = await request<Staff[]>('/api/users/', {
    method: 'GET',
    params: department ? { department } : {},
  });
  return list || [];
}

export async function fetchDepartments(): Promise<string[]> {
  try {
    const list = await request<string[]>('/api/users/departments', { method: 'GET' });
    return list || [];
  } catch {
    return [];
  }
}

/* ---------- 报告 ---------- */
export interface ReportItem {
  id: number;
  report_type: 'daily' | 'weekly';
  title: string;
  report_date: string;
  share_url: string;
  push_status: string;
  note?: string;
  created_at: string;
}

export interface ReportDetail extends ReportItem {
  html_content: string;
}

export interface ReportListResult {
  total: number;
  items: ReportItem[];
}

export async function generateReport(params: { report_type: string; date: string; note?: string }) {
  return request('/api/reports/generate', { method: 'POST', data: params });
}

export async function fetchReports(params?: {
  report_type?: string;
  page?: number;
  page_size?: number;
}) {
  return request<ReportListResult>('/api/reports/', { method: 'GET', params });
}

export async function fetchReportDetail(id: number) {
  return request<ReportDetail>(`/api/reports/${id}`, { method: 'GET' });
}

export async function pushReport(reportId: number, params?: { base_url?: string }) {
  return request<{ success: boolean; message: string; push_status: string; pushed_at: string | null }>(
    `/api/reports/${reportId}/push`,
    { method: 'POST', data: params || {} },
  );
}

export async function fetchStaffDetail(id: number): Promise<StaffDetail> {
  // 后端暂未提供聚合 detail 接口，前端基于 activities 与 users 聚合
  const [users, activities] = await Promise.all([
    fetchStaff(),
    fetchActivities({ user_id: id, page: 1, page_size: 50 }),
  ]);
  const staff = users.find((u) => u.id === id) || { id, name: `员工 #${id}` };
  const recent = activities.list;
  const days = new Set(recent.map((a) => a.activity_date.slice(0, 10)));
  const visits = recent.filter((a) => a.action_type === 'client_visit').length;
  const opps = new Set(recent.map((a) => a.opportunity_id).filter(Boolean));
  return {
    staff,
    active_days: days.size,
    visit_count: visits,
    opportunity_count: opps.size,
    recent_activities: recent,
  };
}

/* ---------- 资讯中心 ---------- */

export interface IntelligenceItem {
  id: number;
  category: 'bidding' | 'news' | 'competitor' | 'ai';
  title: string;
  content?: string;
  summary?: string;
  source?: string;
  source_url?: string;
  published_at?: string;
  relevance_score?: number;
  extra_data?: Record<string, any>;
  is_pushed: boolean;
  created_at: string;
}

export interface IntelligenceStats {
  total: number;
  by_category: Record<string, number>;
  today_count: number;
  latest_crawl: Record<string, string | null>;
}

export interface IntelligenceListParams {
  category?: string;
  keyword?: string;
  source?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export interface CrawlerStatus {
  name: string;
  category: string;
  label: string;
  total_collected: number;
  last_run_at: string | null;
  status: string;
}

export interface CrawlRunResult {
  crawler_name: string;
  total_found: number;
  new_saved: number;
  duplicates_skipped: number;
  errors: number;
  message: string;
}

export async function fetchIntelligence(
  params: IntelligenceListParams,
): Promise<{ items: IntelligenceItem[]; total: number }> {
  const resp = await request<{ items: IntelligenceItem[]; total: number }>(
    '/api/intelligence/',
    { method: 'GET', params },
  );
  return resp || { items: [], total: 0 };
}

export async function fetchIntelligenceStats(): Promise<IntelligenceStats> {
  return request<IntelligenceStats>('/api/intelligence/stats', { method: 'GET' });
}

export async function fetchCrawlerStatus(): Promise<CrawlerStatus[]> {
  const resp = await request<CrawlerStatus[]>('/api/crawlers/status', { method: 'GET' });
  return resp || [];
}

export async function triggerCrawler(name: string): Promise<CrawlRunResult> {
  return request<CrawlRunResult>(`/api/crawlers/${name}/run`, { method: 'POST' });
}

export async function triggerAllCrawlers(): Promise<CrawlRunResult[]> {
  return request<CrawlRunResult[]>('/api/crawlers/run-all', { method: 'POST' });
}

/* ---------- 每日速递 ---------- */

export interface ExpressSection {
  type: string;
  category: string;
  count: number;
}

export interface ExpressItem {
  id: number;
  express_date: string;
  title: string;
  sections: ExpressSection[];
  push_status: string;
  pushed_at: string | null;
  created_at: string;
}

export interface ExpressDetail extends ExpressItem {
  html_content: string;
}

export async function fetchExpressList(params?: {
  page?: number;
  page_size?: number;
}): Promise<{ items: ExpressItem[]; total: number }> {
  const resp = await request<{ items: ExpressItem[]; total: number }>(
    '/api/express/',
    { method: 'GET', params },
  );
  return resp || { items: [], total: 0 };
}

export async function fetchExpressDetail(id: number): Promise<ExpressDetail> {
  return request<ExpressDetail>(`/api/express/${id}`, { method: 'GET' });
}

export async function generateExpress(params: { date: string }): Promise<ExpressItem> {
  return request<ExpressItem>('/api/express/generate', { method: 'POST', data: params });
}

export async function pushExpress(expressId: number, params?: { base_url?: string; skip_screenshot?: boolean }) {
  return request<{
    success: boolean;
    message: string;
    push_status: string;
    pushed_at: string | null;
    screenshot_path?: string;
    screenshot_error?: string;
  }>(`/api/express/${expressId}/push`, { method: 'POST', data: params || {} });
}

/* ---------- 标讯速递 ---------- */

export interface BiddingExpressSummary {
  status: string;
  express_date?: string;
  total?: number;
  groups?: { subtype: string; label: string; count: number }[];
  high_value_count?: number;
  priority_count?: number;
  message?: string;
}

export async function generateBiddingExpress(params?: { date?: string }) {
  return request<BiddingExpressSummary>('/api/bidding-express/generate', { method: 'POST', data: params || {} });
}

export async function getLatestBiddingExpress() {
  return request<BiddingExpressSummary>('/api/bidding-express/latest', { method: 'GET' });
}

export async function pushBiddingExpress(params?: { base_url?: string }) {
  return request<{ success: boolean; message: string; total: number; express_date: string }>(
    '/api/bidding-express/push',
    { method: 'POST', data: params || {} },
  );
}

/* ---------- 管理中心：爬虫配置 ---------- */

export interface CrawlerSourceItem {
  id: number;
  category: string;
  name: string;
  url: string;
  base_url?: string;
  selectors?: Record<string, string>;
  is_active: boolean;
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

export async function fetchLLMStats() {
  return request('/api/llm/stats', { method: 'GET' });
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

export async function updateDingtalkConfig(data: { webhook_url?: string; secret?: string; app_key?: string; app_secret?: string }) {
  return request('/api/settings/dingtalk', { method: 'PUT', data });
}

export async function testDingtalk() {
  return request('/api/settings/dingtalk/test', { method: 'POST' });
}

export async function fetchSystemInfo() {
  return request('/api/settings/system', { method: 'GET' });
}
