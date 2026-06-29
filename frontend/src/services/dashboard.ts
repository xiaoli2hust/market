import { request } from '@@/exports';

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
