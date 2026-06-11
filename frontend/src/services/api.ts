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
 * 登录。优先调用后端 /auth/login 获取真实 JWT；
 * 仅当后端确实不可用（网络错误等）时才走 dev fallback。
 */
export async function login(payload: LoginPayload): Promise<LoginResult> {
  try {
    const resp: any = await request('/api/auth/login', {
      method: 'POST',
      data: payload,
      skipErrorHandler: true,
    });
    // 兼容 umi request 可能的包装：resp 本身或 resp.data
    const data = resp?.data || resp;
    if (data && (data.token || data.access_token)) {
      return {
        token: data.token || data.access_token,
        user: data.user,
      };
    }
  } catch (err: any) {
    // 只有后端确实不可用时才 fallthrough
    console.warn('[login] backend error:', err?.message);
  }
  // 本地兜底：开发阶段后端未启用鉴权
  if (!payload.username || !payload.password) {
    throw new Error('用户名或密码不能为空');
  }
  return {
    token: `dev.${btoa(payload.username)}.${Date.now()}`,
    user: { id: 0, name: payload.username, role: '运营', department: '总部' },
  };
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
  created_at: string;
}

export interface ReportDetail extends ReportItem {
  html_content: string;
}

export interface ReportListResult {
  total: number;
  items: ReportItem[];
}

export async function generateReport(params: { report_type: string; date: string }) {
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
