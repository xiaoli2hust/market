import React from 'react';
import { Empty, Tag } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  BotBroadcastPayload,
  BotBroadcastStatus,
  BotEvidenceRecord,
  BotMessageType,
} from '@/services/api';

export const PAGE_SIZE = 10;

export const STATUS_META: Record<BotBroadcastStatus, { label: string; color: string; icon: React.ReactNode }> = {
  draft: { label: '草稿', color: 'default', icon: <ClockCircleOutlined /> },
  sending: { label: '发送中', color: 'processing', icon: <FieldTimeOutlined /> },
  sent: { label: '已发送', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '发送失败', color: 'error', icon: <ExclamationCircleOutlined /> },
};

export const NOTICE_TYPE_OPTIONS = [
  { value: 'general', label: '普通通知' },
  { value: 'daily_report', label: '日报周报' },
  { value: 'market_digest', label: '市场速递' },
  { value: 'bidding_alert', label: '标讯提醒' },
  { value: 'task_followup', label: '任务提醒' },
];

export const MESSAGE_TYPE_OPTIONS: Array<{ value: BotMessageType; label: string }> = [
  { value: 'markdown', label: '图文排版' },
  { value: 'text', label: '纯文本' },
];

export const DEFAULT_BROADCAST_FORM: Partial<BroadcastFormValues> = {
  message_type: 'markdown',
  notice_type: 'general',
  target_type: 'configured_group',
  at_all: false,
};

export const DEFAULT_KNOWLEDGE_FORM: Partial<KnowledgeFormValues> = {
  category: 'general',
  visibility_scope: 'all_bots',
  review_status: 'approved',
};

export const KNOWLEDGE_CATEGORIES = [
  { value: 'general', label: '通用资料' },
  { value: 'product', label: '产品方案' },
  { value: 'spatial_data', label: '空间数据' },
  { value: 'policy', label: '政策制度' },
  { value: 'weekly_report', label: '周报材料' },
  { value: 'customer', label: '客户资料' },
];

export type BroadcastFormValues = BotBroadcastPayload & { notice_type?: string };
export type KnowledgeFormValues = {
  title: string;
  category: string;
  text_content: string;
  owner_profile_key?: string;
  visibility_scope?: string;
  review_status?: string;
  tags_input?: string;
};
export type ProfileFormValues = {
  profile_key: string;
  name: string;
  description?: string;
  default_role?: string;
  status?: string;
  allowed_skills?: string[];
};
export type ChannelFormValues = {
  channel_key?: string;
  channel_name: string;
  channel_type?: string;
  bot_profile_key: string;
  external_id?: string;
  status?: string;
};
export type AdapterFormValues = {
  adapter_key?: string;
  channel_type: string;
  name: string;
  status?: string;
  event_mode?: string;
  auth_scheme?: string;
  signing_required?: boolean;
  rate_limit_per_minute?: number;
  capabilities_input?: string;
};
export type InboundFormValues = { channel_key?: string; sender_name?: string; content: string };
export type HandoffFormValues = { inbox_id: string; assignee_name: string; reason?: string };
export type TaskFormValues = {
  title: string;
  task_type?: string;
  profile_key: string;
  schedule_type?: string;
  prompt?: string;
};
export type ApprovalFormValues = { title: string; action_type?: string; profile_key?: string; content?: string };
export type TestCaseFormValues = {
  name: string;
  profile_key: string;
  input_text: string;
  conversation_turns_input?: string;
  expected_skills?: string[];
  expected_contains_input?: string;
  required_evidence?: boolean;
  priority?: string;
};
export type CorrectionFormValues = { phrase: string; profile_key?: string; expected_skills?: string[]; notes?: string };
export type CollaborationFormValues = {
  title?: string;
  lead_profile_key: string;
  participant_profiles?: string[];
  input_text: string;
};
export type ReleaseFormValues = { profile_key: string; environment_key?: string; change_note?: string };
export type FeedbackFormValues = {
  rating: string;
  profile_key?: string;
  conversation_id?: string;
  reason?: string;
  comment?: string;
};
export type KnowledgeSyncFormValues = {
  name: string;
  source_type?: string;
  category?: string;
  schedule_type?: string;
  title?: string;
  text_content?: string;
};
export type ComplianceFormValues = {
  policy_key?: string;
  name: string;
  policy_type?: string;
  status?: string;
  action?: string;
  blocked_terms_input?: string;
};

export const EvidenceList: React.FC<{ evidence: BotEvidenceRecord[] }> = ({ evidence }) => {
  if (!evidence.length) return <Empty description="暂无证据" />;
  return (
    <div className="bot-evidence-list">
      {evidence.slice(0, 8).map((item) => (
        <div className="bot-evidence" key={item.evidence_id}>
          <div>
            <strong>{item.title || item.evidence_id}</strong>
            <Tag>{item.source_type}</Tag>
          </div>
          <p>{item.snippet || item.source || '已命中证据'}</p>
          <span>{item.source || item.category || '内部数据'} {item.published_at ? `· ${item.published_at}` : ''}</span>
        </div>
      ))}
    </div>
  );
};

export function formatTime(value?: string | null): string {
  if (!value) return '—';
  return dayjs(value).format('YYYY-MM-DD HH:mm');
}

export function splitTextList(value?: string): string[] {
  return String(value || '')
    .split(/[,，;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20);
}

export function parseConversationTurns(value?: string): Array<{ role: string; content: string }> {
  return String(value || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(用户|user|机器人|assistant|系统|system)[:：]\s*(.+)$/i);
      if (!match) return { role: 'user', content: line };
      const roleMap: Record<string, string> = {
        用户: 'user',
        user: 'user',
        机器人: 'assistant',
        assistant: 'assistant',
        系统: 'system',
        system: 'system',
      };
      return { role: roleMap[match[1]] || 'user', content: match[2].trim() };
    })
    .filter((item) => item.content)
    .slice(0, 12);
}

