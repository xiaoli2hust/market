import { request } from '@@/exports';
import { CRAWLER_TASK_TIMEOUT_MS } from './common';

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
