import React from 'react';
import dayjs, { Dayjs } from 'dayjs';

export interface FilterState {
  mode: 'daily' | 'weekly' | 'custom';
  currentDate: Dayjs;
  currentWeekStart: Dayjs;
  customRange: [Dayjs, Dayjs];
  range: [Dayjs, Dayjs];
  userId?: number;
  department?: string;
  role?: string;
  actionTypes: string[];
  keyword: string;
}

export function sanitizeHtmlForPreview(html: string): string {
  if (typeof window === 'undefined') return html;
  const doc = new DOMParser().parseFromString(html, 'text/html');
  doc.querySelectorAll('script, iframe, object, embed').forEach((node) => node.remove());
  doc.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc' || value.startsWith('javascript:')) {
        node.removeAttribute(attr.name);
      }
    });
  });
  return doc.documentElement.outerHTML;
}

export function getWeekMonday(value: Dayjs): Dayjs {
  return value.subtract((value.day() + 6) % 7, 'day').startOf('day');
}

export function formatFileSize(bytes?: number): string {
  const value = Number(bytes || 0);
  if (!value) return '0 KB';
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

export const StatCell: React.FC<{
  label: string;
  value: number;
  unit?: string;
  highlight?: boolean;
}> = ({ label, value, unit, highlight }) => (
  <div className={`dash-stat edl-card ${highlight ? 'is-highlight' : ''}`}>
    <div className="edl-stat-label">{label}</div>
    <div className="dash-stat-value">
      <span className="edl-stat-num">{value}</span>
      {unit && <span className="dash-stat-unit">{unit}</span>}
    </div>
  </div>
);

