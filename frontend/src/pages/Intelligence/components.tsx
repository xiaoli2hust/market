import React from 'react';
import { Button, Empty, Tag } from 'antd';
import { ArrowRightOutlined, LinkOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { IntelligenceAnalysisTopItem, IntelligenceEvidenceRecord } from '@/services/api';

const formatWanAmount = (amount?: number) => {
  const value = Number(amount || 0);
  if (!value) return '0万';
  if (value >= 10000) return `${(value / 10000).toFixed(2)}亿`;
  if (value >= 100) return `${value.toFixed(1)}万`;
  return `${value.toFixed(2)}万`;
};

export const ModuleTab: React.FC<{ no: string; title: string; desc: string }> = ({ no, title, desc }) => (
  <div className="intel-module-tab">
    <span className="edl-mono">{no}</span>
    <strong>{title}</strong>
    <small>{desc}</small>
  </div>
);

export const AgentSection: React.FC<{
  eyebrow: string;
  title: string;
  desc: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}> = ({ eyebrow, title, desc, actions, children }) => (
  <section className="intel-agent-section">
    <div className="intel-agent-head">
      <div>
        <div className="edl-eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <p>{desc}</p>
      </div>
      {actions && <div className="intel-agent-actions">{actions}</div>}
    </div>
    {children}
  </section>
);

export const MetricGrid: React.FC<{ metrics: Array<[string, number | string, string]> }> = ({ metrics }) => (
  <div className="intel-analysis-metrics">
    {metrics.map(([label, value, suffix]) => (
      <div key={label}>
        <span className="edl-mono">
          {value}
          {suffix && <small>{suffix}</small>}
        </span>
        <em>{label}</em>
      </div>
    ))}
  </div>
);

export const InsightPanel: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="intel-analysis-block">
    <h3>{title}</h3>
    {children}
  </div>
);

export const DistributionList: React.FC<{
  items: Array<{ name: string; count: number }>;
  tone?: 'red' | 'cyan';
}> = ({ items, tone }) => (
  <div className="intel-distribution">
    {items.length ? items.slice(0, 8).map((item) => (
      <div className="intel-distribution-row" key={item.name}>
        <Tag color={tone === 'red' ? 'red' : tone === 'cyan' ? 'cyan' : undefined}>{item.name}</Tag>
        <div>
          <span style={{ width: `${Math.min(100, item.count * 18)}%` }} />
        </div>
        <em>{item.count}</em>
      </div>
    )) : <p>暂无分布数据</p>}
  </div>
);

export const TopSignalList: React.FC<{
  title: string;
  items: IntelligenceAnalysisTopItem[];
  emptyText: string;
  onOpenData: () => void;
}> = ({ title, items, emptyText, onOpenData }) => (
  <div className="intel-top-signals">
    <div className="intel-top-signals-head">
      <h3>{title}</h3>
      <Button type="link" onClick={onOpenData}>查看数据 <ArrowRightOutlined /></Button>
    </div>
    {items.length ? items.slice(0, 8).map((item) => (
      <button className="intel-top-signal" type="button" key={item.id} onClick={onOpenData}>
        <strong>{item.title}</strong>
        <span>
          贴合度 {Math.round(item.score || 0)}
          {item.amount_wan ? ` · ${formatWanAmount(item.amount_wan)}` : ''}
          {item.location ? ` · ${item.location}` : ''}
        </span>
        {!!item.matched_keywords?.length && (
          <em>{item.matched_keywords.slice(0, 5).join(' / ')}</em>
        )}
      </button>
    )) : <Empty description={emptyText} />}
  </div>
);

export const EvidenceRecordList: React.FC<{
  title: string;
  items: IntelligenceEvidenceRecord[];
  onOpenData: () => void;
}> = ({ title, items, onOpenData }) => (
  <div className="intel-evidence">
    <div className="intel-evidence-head">
      <h3>{title}</h3>
      <Button type="link" onClick={onOpenData}>查看全部 <ArrowRightOutlined /></Button>
    </div>
    {items.length ? items.slice(0, 12).map((item) => (
      <div className="intel-evidence-row" key={item.evidence_id || item.record_id}>
        <div className="intel-evidence-main">
          <Tag>{item.evidence_id}</Tag>
          <strong>{item.title}</strong>
        </div>
        <div className="intel-evidence-meta">
          <span>{item.source || '外部信号'}</span>
          <span>评分 {Math.round(item.score || 0)}</span>
          {!!item.amount_wan && <span>{formatWanAmount(item.amount_wan)}</span>}
          <span>{item.published_at ? dayjs(item.published_at).format('MM/DD') : '未标日期'}</span>
          {item.source_url && <LinkOutlined onClick={() => window.open(item.source_url || '', '_blank', 'noopener,noreferrer')} />}
        </div>
        {!!item.matched_keywords?.length && (
          <div className="intel-evidence-keywords">
            {item.matched_keywords.slice(0, 6).map((kw: string) => <Tag key={kw}>{kw}</Tag>)}
          </div>
        )}
      </div>
    )) : <Empty description="暂无可追溯证据" />}
  </div>
);
