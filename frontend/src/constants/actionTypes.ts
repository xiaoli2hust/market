/**
 * 行为类型 → 中文 + 视觉色标
 * 色板使用低饱和的"宋瓷"色系，与编辑式视觉保持一致
 */
export interface ActionTypeMeta {
  value: string;
  label: string;
  color: string; // antd Tag color name 或 hex
  ink: string; // 自定义印章色
}

export const ACTION_TYPES: ActionTypeMeta[] = [
  { value: 'client_visit', label: '拜访客户', color: 'blue', ink: '#2B5F8A' },
  { value: 'opportunity_track', label: '商机跟进', color: 'orange', ink: '#C77A2E' },
  { value: 'proposal_write', label: '方案撰写', color: 'cyan', ink: '#3F8B8B' },
  { value: 'project_advance', label: '项目推进', color: 'green', ink: '#3F7A4A' },
  { value: 'channel_expand', label: '渠道拓展', color: 'purple', ink: '#6A4C8A' },
  { value: 'payment_follow', label: '回款跟进', color: 'red', ink: '#C53A2C' },
  // 内部协作（使用 other 兜底）
  { value: 'tech_exchange', label: '技术交流', color: 'geekblue', ink: '#3B4A6B' },
  { value: 'poc_test', label: 'POC测试', color: 'volcano', ink: '#A8482A' },
  { value: 'bidding', label: '招投标', color: 'magenta', ink: '#9C3D6B' },
  { value: 'contract_negotiate', label: '合同谈判', color: 'gold', ink: '#A37A1F' },
  { value: 'client_maintain', label: '客户维护', color: 'lime', ink: '#5F7A2E' },
  { value: 'other', label: '内部协作', color: 'default', ink: '#7A6F62' },
];

export const ACTION_TYPE_MAP: Record<string, ActionTypeMeta> = ACTION_TYPES.reduce(
  (acc, t) => {
    acc[t.value] = t;
    return acc;
  },
  {} as Record<string, ActionTypeMeta>,
);

export function getActionMeta(value?: string): ActionTypeMeta {
  if (!value) return ACTION_TYPE_MAP.other;
  return ACTION_TYPE_MAP[value] || { value, label: value, color: 'default', ink: '#7A6F62' };
}
