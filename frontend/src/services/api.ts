import { request } from '@@/exports';

/* ---------- 类型 ---------- */
export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  token?: string;
  user?: {
    id: number;
    name: string;
    role?: string;
    permissions?: string[];
    department?: string;
    security_warnings?: string[];
    must_change_password?: boolean;
  };
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
const SESSION_HINT_KEY = 'market_session_active';
const USER_KEY = 'market_user';
const LONG_TASK_TIMEOUT_MS = 300000;
const CRAWLER_TASK_TIMEOUT_MS = 1800000;

export function hasAuthSession(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(SESSION_HINT_KEY) === '1';
}

export function setAuth(user?: LoginResult['user']) {
  localStorage.setItem(SESSION_HINT_KEY, '1');
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(SESSION_HINT_KEY);
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

export async function fetchCurrentUser(): Promise<LoginResult['user'] | null> {
  try {
    const resp = await fetch('/api/auth/me', {
      method: 'GET',
      credentials: 'same-origin',
    });
    if (!resp.ok) {
      clearAuth();
      return null;
    }
    const data = await resp.json();
    const user = {
      id: data?.id || 0,
      name: data?.name || data?.username || '未命名用户',
      role: data?.role || 'viewer',
      permissions: data?.permissions || [],
      department: data?.department || '管理中心',
      security_warnings: data?.security_warnings || [],
      must_change_password: Boolean(data?.must_change_password),
    };
    setAuth(user);
    return user;
  } catch {
    clearAuth();
    return null;
  }
}

export async function logout() {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });
  } finally {
    clearAuth();
  }
}

const ROLE_PERMISSIONS: Record<string, string[]> = {
  super_admin: ['*'],
  admin: [
    'dashboard:view',
    'dashboard:export',
    'reports:view',
    'reports:generate',
    'intelligence:view',
    'opportunities:view',
    'opportunities:manage',
    'bot:view',
    'bot:broadcast',
    'management:view',
    'management:crawler',
    'management:llm',
    'management:users',
    'management:settings',
    'management:express',
  ],
  viewer: ['dashboard:view', 'intelligence:view', 'opportunities:view'],
};

export const PERMISSION_LABELS: Record<string, string> = {
  'dashboard:view': '查看日报周报',
  'dashboard:export': '导出日报周报',
  'reports:view': '查看汇报材料',
  'reports:generate': '生成与推送汇报',
  'intelligence:view': '查看市场洞察',
  'opportunities:view': '查看商机中心',
  'opportunities:manage': '确认与流转线索',
  'bot:view': '查看机器人中心',
  'bot:broadcast': '发送机器人群发消息',
  'management:view': '进入管理中心',
  'management:crawler': '管理采集任务',
  'management:llm': '管理模型与提示词',
  'management:users': '管理账号权限',
  'management:settings': '管理接口与密钥',
  'management:express': '生成标讯速递',
};

export function getPermissionLabel(permission: string): string {
  if (permission === '*') return '全部权限';
  return PERMISSION_LABELS[permission] || '未登记权限';
}

export function userHasPermission(user: LoginResult['user'] | null | undefined, permission: string): boolean {
  const permissions = user?.permissions?.length
    ? user.permissions
    : (ROLE_PERMISSIONS[user?.role || 'viewer'] || ROLE_PERMISSIONS.viewer);
  return permissions.includes('*') || permissions.includes(permission);
}

export function getApiErrorMessage(error: any, fallback: string): string {
  return (
    error?.data?.detail
    || error?.data?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback
  );
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
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody?.detail || `登录失败 (${resp.status})`);
    }

    const data = await resp.json();
    return {
      token: data?.token || data?.access_token,
      user: data?.user || { id: 0, name: payload.username, role: 'admin', department: '总部' },
    };
  } catch (err: any) {
    if (err?.message?.includes('Failed to fetch') || err?.message?.includes('NetworkError')) {
      throw new Error('无法连接到后端服务，请确认后端已启动');
    }
    throw err;
  }
}

export async function changeCurrentPassword(data: {
  current_password: string;
  new_password: string;
}) {
  return request('/api/auth/change-password', { method: 'POST', data });
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
    keyword: params.keyword,
  };
  Object.keys(query).forEach((k) => query[k] === undefined && delete query[k]);

  const resp = await request<{ items?: ActivityItem[]; list?: ActivityItem[]; total?: number } | ActivityItem[]>('/api/activities/', {
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

  const total = Array.isArray(resp) ? list.length : (resp?.total ?? list.length);
  return { list: list || [], total };
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
  version: number;
  status: 'draft' | 'published' | 'superseded' | string;
  note?: string;
  pushed_at?: string | null;
  superseded_at?: string | null;
  created_at: string;
}

export interface ReportDetail extends ReportItem {
  html_content: string;
}

export interface ReportListResult {
  total: number;
  items: ReportItem[];
}

export interface DepartmentWeeklyReportItem {
  id: number;
  department: string;
  week_start: string;
  week_end: string;
  title: string;
  file_name: string;
  source_type: string;
  content_length: number;
  uploaded_by?: string | null;
  status: string;
  created_at: string;
  updated_at?: string | null;
}

export interface DepartmentWeeklyReportDetail extends DepartmentWeeklyReportItem {
  html_content: string;
  text_content?: string | null;
}

export interface DepartmentWeeklyReportListResult {
  total: number;
  items: DepartmentWeeklyReportItem[];
}

export async function generateReport(params: { report_type: string; date: string; note?: string }) {
  return request('/api/reports/generate', {
    method: 'POST',
    data: params,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
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
  return request<{ success: boolean; message: string; push_status: string; status: string; version: number; pushed_at: string | null }>(
    `/api/reports/${reportId}/push`,
    { method: 'POST', data: params || {}, timeout: LONG_TASK_TIMEOUT_MS },
  );
}

export async function fetchDepartmentWeeklyReports(params?: {
  department?: string;
  week_start?: string;
  page?: number;
  page_size?: number;
}) {
  return request<DepartmentWeeklyReportListResult>('/api/reports/department-weekly', { method: 'GET', params });
}

export async function fetchDepartmentWeeklyReportDetail(id: number) {
  return request<DepartmentWeeklyReportDetail>(`/api/reports/department-weekly/${id}`, { method: 'GET' });
}

export async function uploadDepartmentWeeklyReport(params: {
  department: string;
  week_start: string;
  title?: string;
  file: File;
}) {
  const form = new FormData();
  form.append('department', params.department);
  form.append('week_start', params.week_start);
  if (params.title) form.append('title', params.title);
  form.append('file', params.file);
  const resp = await fetch('/api/reports/department-weekly/upload', {
    method: 'POST',
    credentials: 'same-origin',
    body: form,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw Object.assign(new Error(data?.detail || data?.message || '部门周报上传失败'), { data });
  }
  return data as DepartmentWeeklyReportItem;
}

export async function deleteDepartmentWeeklyReport(id: number) {
  return request<{ success: boolean; id: number }>(`/api/reports/department-weekly/${id}`, { method: 'DELETE' });
}

export async function fetchStaffDetail(id: number): Promise<StaffDetail> {
  const detail = await request<{
    staff: Staff;
    stats?: {
      active_days?: number;
      visit_count?: number;
      opportunity_count?: number;
    };
    recent_activities?: ActivityItem[];
  }>(`/api/staff/${id}`, { method: 'GET' });
  return {
    staff: detail.staff,
    active_days: detail.stats?.active_days || 0,
    visit_count: detail.stats?.visit_count || 0,
    opportunity_count: detail.stats?.opportunity_count || 0,
    recent_activities: detail.recent_activities || [],
  };
}

/* ---------- 市场洞察 ---------- */

export interface IntelligenceItem {
  id: number;
  category: 'bidding' | 'policy' | 'news' | 'competitor' | 'ai' | string;
  title: string;
  content?: string;
  summary?: string;
  source?: string;
  source_url?: string;
  published_at?: string;
  relevance_score?: number;
  amount_wan?: number | null;
  amount_display?: string | null;
  buyer?: string | null;
  region?: string | null;
  notice_type?: string | null;
  matched_keywords?: string[] | null;
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
  sort_by?: 'published_at' | 'amount' | 'relevance' | 'created_at' | string;
  sort_order?: 'asc' | 'desc' | string;
  page?: number;
  page_size?: number;
}

export interface IntelligenceAnalysisCounter {
  name: string;
  count: number;
}

export interface IntelligenceAnalysisTopItem {
  evidence_id?: string;
  id: number;
  title: string;
  score: number;
  source?: string;
  source_url?: string | null;
  published_at?: string | null;
  topics?: string[];
  customer_types?: string[];
  recommended_action?: string | null;
  amount_wan?: number;
  buyer?: string | null;
  region?: string | null;
  notice_type?: string | null;
  matched_keywords?: string[];
  location?: string | null;
  summary?: string | null;
}

export interface IntelligenceEvidenceRecord {
  evidence_id: string;
  record_id: number;
  category: string;
  title: string;
  source?: string | null;
  source_url?: string | null;
  published_at?: string | null;
  created_at?: string | null;
  score: number;
  amount_wan?: number;
  buyer?: string | null;
  region?: string | null;
  notice_type?: string | null;
  matched_keywords?: string[];
  summary?: string | null;
}

export interface IntelligenceAnalysis {
  category: string;
  label: string;
  period: 'week' | 'month' | string;
  range: { start: string; end: string };
  summary: {
    total: number;
    relevant: number;
    ignored: number;
    avg_score: number;
    amount_total_wan: number;
    relevance_threshold?: number;
    evidence_count?: number;
  };
  distribution: {
    topics: IntelligenceAnalysisCounter[];
    customer_types: IntelligenceAnalysisCounter[];
    regions: IntelligenceAnalysisCounter[];
    actions: IntelligenceAnalysisCounter[];
    keywords?: IntelligenceAnalysisCounter[];
    notice_types?: IntelligenceAnalysisCounter[];
    timeline: IntelligenceAnalysisCounter[];
  };
  findings: string[];
  recommendations: string[];
  top_items: IntelligenceAnalysisTopItem[];
  evidence_records?: IntelligenceEvidenceRecord[];
}

export interface CrawlerStatus {
  name: string;
  category: string;
  label: string;
  total_collected: number;
  effective_count?: number;
  filtered_count?: number;
  last_run_at: string | null;
  last_item_at?: string | null;
  last_run_stats?: CrawlerRunLog | Record<string, any> | null;
  active_sources?: number;
  source_details?: Array<{
    name: string;
    type?: string;
    url?: string | null;
    base_url?: string | null;
    is_active?: boolean;
    scope?: string;
    strategy?: string;
    capability_status?: string;
    capability_reason?: string;
  }>;
  source_breakdown?: Array<{
    name: string;
    count: number;
    latest_item_at?: string | null;
  }>;
  strategy?: {
    source_type?: string;
    fetch_method?: string;
    anti_crawl?: string;
    filter_policy?: string;
    business_scope?: string;
  };
  latest_task_run?: Record<string, any> | null;
  task_lock?: Record<string, any> | null;
  last_error?: string | null;
  status: string;
}

export interface CrawlRunResult {
  crawler_name: string;
  total_found: number;
  new_saved: number;
  duplicates_skipped: number;
  low_score_discarded: number;
  errors: number;
  duration_ms?: number | null;
  message: string;
}

export interface CrawlerRunLog {
  id: number;
  crawler_name: string;
  category: string;
  status: string;
  total_found: number;
  new_saved: number;
  duplicates_skipped: number;
  low_score_discarded: number;
  errors: number;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  extra_data?: Record<string, any> | null;
  created_at: string;
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

export async function fetchIntelligenceAnalysis(params?: {
  category?: string;
  period?: 'week' | 'month';
}): Promise<IntelligenceAnalysis> {
  return request<IntelligenceAnalysis>('/api/intelligence/analysis', {
    method: 'GET',
    params: params || { category: 'bidding', period: 'week' },
  });
}

export async function fetchCrawlerStatus(): Promise<CrawlerStatus[]> {
  const resp = await request<CrawlerStatus[]>('/api/crawlers/status', { method: 'GET' });
  return resp || [];
}

export async function fetchCrawlerRuns(params?: { crawler_name?: string; limit?: number }): Promise<CrawlerRunLog[]> {
  const resp = await request<CrawlerRunLog[]>('/api/crawlers/runs', { method: 'GET', params });
  return resp || [];
}

export async function triggerCrawler(name: string): Promise<CrawlRunResult> {
  return request<CrawlRunResult>(`/api/crawlers/${name}/run`, {
    method: 'POST',
    timeout: CRAWLER_TASK_TIMEOUT_MS,
  });
}

export async function triggerAllCrawlers(): Promise<CrawlRunResult[]> {
  return request<CrawlRunResult[]>('/api/crawlers/run-all', {
    method: 'POST',
    timeout: CRAWLER_TASK_TIMEOUT_MS,
  });
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
  return request<ExpressItem>('/api/express/generate', {
    method: 'POST',
    data: params,
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function pushExpress(expressId: number, params?: { base_url?: string; skip_screenshot?: boolean }) {
  return request<{
    success: boolean;
    message: string;
    push_status: string;
    pushed_at: string | null;
    screenshot_path?: string;
    screenshot_error?: string;
  }>(`/api/express/${expressId}/push`, {
    method: 'POST',
    data: params || {},
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

/* ---------- 标讯速递 ---------- */

export interface BiddingExpressSummary {
  status: string;
  express_date?: string;
  period?: 'day' | 'week' | 'month' | 'all' | string;
  period_label?: string;
  source_total?: number;
  total?: number;
  groups?: { subtype: string; label: string; count: number }[];
  high_value_count?: number;
  priority_count?: number;
  message?: string;
}

export async function generateBiddingExpress(params?: { date?: string; period?: 'day' | 'week' | 'month' | 'all' }) {
  return request<BiddingExpressSummary>('/api/bidding-express/generate', {
    method: 'POST',
    data: params || {},
    timeout: LONG_TASK_TIMEOUT_MS,
  });
}

export async function getLatestBiddingExpress() {
  return request<BiddingExpressSummary>('/api/bidding-express/latest', { method: 'GET' });
}

export async function pushBiddingExpress(params?: { base_url?: string }) {
  return request<{ success: boolean; message: string; total: number; express_date: string; period_label?: string }>(
    '/api/bidding-express/push',
    { method: 'POST', data: params || {}, timeout: LONG_TASK_TIMEOUT_MS },
  );
}

export async function fetchBiddingExpressPreviewHtml(): Promise<string> {
  const resp = await fetch('/api/bidding-express/preview', {
    credentials: 'same-origin',
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.detail || `预览失败 (${resp.status})`);
  }
  return resp.text();
}

/* ---------- G端标讯线索确认 ---------- */

export type OpportunityDecision = 'HIGH_PRIORITY' | 'MEDIUM' | 'LOW' | 'IGNORE';
export type OpportunityStatus = 'new' | 'reviewing' | 'converted' | 'ignored';

export interface OpportunityLead {
  id: number;
  project_name: string;
  buyer?: string | null;
  budget: number;
  score: number;
  decision: OpportunityDecision;
  summary?: string | null;
  why_it_matters: string[];
  risks: string[];
  recommended_action: string[];
  url: string;
  source: string;
  source_category?: string | null;
  procurement_method?: string | null;
  publish_date?: string | null;
  status: OpportunityStatus;
  created_at?: string | null;
  updated_at?: string | null;
  raw_record?: Record<string, any>;
}

export interface OpportunityLeadStats {
  total: number;
  actionable_count: number;
  budget_total: number;
  avg_score: number;
  latest_created_at?: string | null;
  by_decision: Record<string, number>;
  by_status: Record<string, number>;
}

export interface OpportunityLeadListParams {
  decision?: string;
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export async function fetchOpportunityLeads(
  params: OpportunityLeadListParams,
): Promise<{ items: OpportunityLead[]; total: number; page: number; page_size: number }> {
  const resp = await request<{ items: OpportunityLead[]; total: number; page: number; page_size: number }>(
    '/api/opportunity-leads/',
    { method: 'GET', params },
  );
  return resp || { items: [], total: 0, page: params.page || 1, page_size: params.page_size || 20 };
}

export async function fetchOpportunityLeadStats(): Promise<OpportunityLeadStats> {
  return request<OpportunityLeadStats>('/api/opportunity-leads/stats', { method: 'GET' });
}

export async function discoverOpportunityLeads(params?: {
  pages_per_source?: number;
  persist?: boolean;
  use_fallback?: boolean;
}) {
  return request<{
    total: number;
    saved: number;
    updated: number;
    decision_counts: Record<string, number>;
    items: OpportunityLead[];
    stats?: OpportunityLeadStats;
  }>('/api/opportunity-leads/discover', {
    method: 'POST',
    timeout: LONG_TASK_TIMEOUT_MS,
    data: { pages_per_source: 4, persist: true, use_fallback: true, ...(params || {}) },
  });
}

export async function updateOpportunityLeadStatus(id: number, status: OpportunityStatus) {
  return request<OpportunityLead>(`/api/opportunity-leads/${id}/status`, {
    method: 'PUT',
    data: { status },
  });
}

/* ---------- 机器人中心 ---------- */

export type BotBroadcastStatus = 'draft' | 'sending' | 'sent' | 'failed';
export type BotMessageType = 'markdown' | 'text';

export interface BotBroadcastItem {
  id: number;
  title: string;
  content: string;
  message_type: BotMessageType;
  target_type: string;
  target_summary?: string | null;
  target_payload?: Record<string, any>;
  at_all: boolean;
  status: BotBroadcastStatus;
  created_by?: number | null;
  created_by_name?: string | null;
  sent_by?: number | null;
  sent_by_name?: string | null;
  sent_at?: string | null;
  result_message?: string | null;
  result_payload?: Record<string, any>;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotBroadcastPayload {
  title: string;
  content: string;
  message_type?: BotMessageType;
  target_type?: 'configured_group';
  target_payload?: Record<string, any>;
  at_all?: boolean;
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

/* ---------- 管理中心：爬虫配置 ---------- */

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

export async function fetchSystemInfo() {
  return request('/api/settings/system', { method: 'GET' });
}
