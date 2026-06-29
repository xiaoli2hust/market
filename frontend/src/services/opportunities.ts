import { request } from '@@/exports';
import { LONG_TASK_TIMEOUT_MS } from './common';

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
