import { request } from '@@/exports';
import { LONG_TASK_TIMEOUT_MS } from './common';

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
