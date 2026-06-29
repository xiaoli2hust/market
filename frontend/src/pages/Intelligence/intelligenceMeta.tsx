import React from 'react';
import {
  EyeOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import type { IntelligenceItem } from '@/services/api';

export const PAGE_SIZE = 12;
export const INTELLIGENCE_CRAWLER_MESSAGE_KEY = 'intelligence-crawler-run';
export type DataSortBy = 'published_at' | 'amount' | 'relevance' | 'created_at';
export type DataSortOrder = 'asc' | 'desc';

export const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  bidding: { label: '标讯数据', color: '#f5222d', icon: <FileSearchOutlined /> },
  policy: { label: '政策法规', color: '#13c2c2', icon: <GlobalOutlined /> },
  news: { label: '市场线索', color: '#1890ff', icon: <GlobalOutlined /> },
  competitor: { label: '竞对监控', color: '#fa8c16', icon: <EyeOutlined /> },
  ai: { label: '行业知识', color: '#722ed1', icon: <RobotOutlined /> },
};

export const DATA_CATEGORY_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'bidding', label: '标讯' },
  { value: 'policy', label: '政策' },
  { value: 'news', label: '市场' },
  { value: 'competitor', label: '竞对' },
  { value: 'ai', label: '行业知识' },
];

export const formatWanAmount = (amount?: number) => {
  const value = Number(amount || 0);
  if (!value) return '0万';
  if (value >= 10000) return `${(value / 10000).toFixed(2)}亿`;
  if (value >= 100) return `${value.toFixed(1)}万`;
  return `${value.toFixed(2)}万`;
};

export const itemAmountWan = (item: IntelligenceItem) => Number(item.amount_wan ?? item.extra_data?.amount_wan ?? 0);

export const itemAmountText = (item: IntelligenceItem) => {
  const explicit = item.amount_display || item.extra_data?.amount_display;
  if (explicit) return String(explicit);
  const amount = itemAmountWan(item);
  return amount > 0 ? formatWanAmount(amount) : '—';
};

export const itemSourceText = (item: IntelligenceItem) => (
  item.category === 'bidding' ? '标讯数据' : item.source || item.extra_data?.source || '外部信号'
);

export const tableSortOrder = (active: boolean, order: DataSortOrder) => (
  active ? (order === 'asc' ? 'ascend' : 'descend') : undefined
) as 'ascend' | 'descend' | undefined;

export const uniqueTexts = (...groups: Array<string[] | undefined>) => {
  const seen = new Set<string>();
  const result: string[] = [];
  groups.flat().forEach((text) => {
    const value = String(text || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result;
};
