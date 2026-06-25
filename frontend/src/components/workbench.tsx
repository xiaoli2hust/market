import React from 'react';
import { Button, Space, Tag } from 'antd';
import type { ButtonProps } from 'antd';
import './workbench.less';

export interface WorkbenchMetric {
  label: string;
  value: React.ReactNode;
  suffix?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: 'red' | 'blue' | 'green' | 'gold' | 'purple' | 'neutral';
  hint?: React.ReactNode;
}

export interface WorkbenchAction extends ButtonProps {
  label: React.ReactNode;
}

export const WorkbenchPageHeader: React.FC<{
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  accent?: React.ReactNode;
  description?: React.ReactNode;
  actions?: WorkbenchAction[];
  extra?: React.ReactNode;
}> = ({ eyebrow, title, accent, description, actions, extra }) => (
  <div className="wb-page-head">
    <div className="wb-page-copy">
      {eyebrow && <div className="wb-eyebrow">{eyebrow}</div>}
      <h1>
        {title}
        {accent && <span>{accent}</span>}
      </h1>
      {description && <p>{description}</p>}
    </div>
    {(actions?.length || extra) && (
      <div className="wb-page-actions">
        {extra}
        {!!actions?.length && (
          <Space wrap>
            {actions.map(({ label, ...props }, index) => (
              <Button key={String(index)} {...props}>
                {label}
              </Button>
            ))}
          </Space>
        )}
      </div>
    )}
  </div>
);

export const WorkbenchMetricGrid: React.FC<{ metrics: WorkbenchMetric[] }> = ({ metrics }) => (
  <div className="wb-metric-grid">
    {metrics.map((metric) => (
      <div className={`wb-metric-card tone-${metric.tone || 'neutral'}`} key={metric.label}>
        <div className="wb-metric-top">
          <span>{metric.label}</span>
          {metric.icon && <i>{metric.icon}</i>}
        </div>
        <strong>
          {metric.value}
          {metric.suffix && <em>{metric.suffix}</em>}
        </strong>
        {metric.hint && <small>{metric.hint}</small>}
      </div>
    ))}
  </div>
);

export const WorkbenchSection: React.FC<{
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, description, action, children, className }) => (
  <section className={`wb-section ${className || ''}`}>
    <div className="wb-section-head">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="wb-section-action">{action}</div>}
    </div>
    {children}
  </section>
);

export const WorkbenchStatusRail: React.FC<{
  items: Array<{
    label: React.ReactNode;
    value: React.ReactNode;
    status?: 'good' | 'warn' | 'danger' | 'muted';
    meta?: React.ReactNode;
  }>;
}> = ({ items }) => (
  <div className="wb-status-rail">
    {items.map((item) => (
      <div className={`wb-status-item status-${item.status || 'muted'}`} key={String(item.label)}>
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        {item.meta && <small>{item.meta}</small>}
      </div>
    ))}
  </div>
);

export const WorkbenchTagLine: React.FC<{
  label: React.ReactNode;
  tags: Array<{ label: React.ReactNode; color?: string }>;
}> = ({ label, tags }) => (
  <div className="wb-tag-line">
    <span>{label}</span>
    <div>
      {tags.length ? tags.map((tag, index) => (
        <Tag key={String(index)} color={tag.color}>{tag.label}</Tag>
      )) : <Tag>暂无</Tag>}
    </div>
  </div>
);
