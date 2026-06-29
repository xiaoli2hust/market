export type BotBroadcastStatus = 'draft' | 'sending' | 'sent' | 'failed';
export type BotMessageType = 'markdown' | 'text';

export interface BotOverview {
  profiles: number;
  enabled_skills: number;
  conversations: number;
  knowledge_files: number;
  pending_approvals?: number;
  active_tasks?: number;
  failed_evaluations?: number;
  collaboration_runs?: number;
  open_inbox?: number;
  open_handoffs?: number;
  enabled_adapters?: number;
  open_feedback?: number;
  latest_run_at?: string | null;
}

export interface BotProfile {
  id: number;
  profile_key: string;
  name: string;
  description?: string | null;
  system_prompt?: string | null;
  default_role?: string | null;
  status: string;
  allowed_skills: string[];
  config?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotSkill {
  id: number;
  skill_key: string;
  name: string;
  category: string;
  description?: string | null;
  trigger_scenarios: string[];
  input_contract: Record<string, any>;
  output_contract: Record<string, any>;
  evidence_rules: Record<string, any>;
  required_permission?: string | null;
  enabled: boolean;
  implementation_status: string;
  config?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotConversation {
  id: number;
  conversation_id: string;
  profile_key: string;
  title?: string | null;
  simulated_user_role?: string | null;
  channel_type: string;
  status: string;
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotMessage {
  id: number;
  role: 'user' | 'assistant' | 'system' | string;
  content: string;
  content_type: string;
  source?: string | null;
  meta?: Record<string, any>;
  created_at?: string | null;
}

export interface BotEvidenceRecord {
  evidence_id: string;
  source_type: string;
  title?: string;
  source?: string | null;
  category?: string | null;
  source_url?: string | null;
  published_at?: string | null;
  amount_wan?: number | null;
  buyer?: string | null;
  region?: string | null;
  score?: number | null;
  snippet?: string | null;
  record_id?: number | null;
}

export interface BotToolCall {
  id?: number;
  skill_run_id?: number;
  tool_name: string;
  status: string;
  input_payload?: Record<string, any>;
  output_payload?: Record<string, any>;
  duration_ms?: number | null;
  error_message?: string | null;
  created_at?: string | null;
}

export interface BotSkillRun {
  id?: number;
  run_id: string;
  conversation_pk?: number | null;
  message_id?: number | null;
  profile_key: string;
  skill_key: string;
  skill_name?: string;
  status: string;
  input_payload?: Record<string, any>;
  output_payload?: Record<string, any>;
  output?: Record<string, any>;
  evidence_records: BotEvidenceRecord[];
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  tool_calls?: BotToolCall[];
}

export interface BotChatTestResult {
  conversation: BotConversation;
  user_message: BotMessage;
  assistant_message: BotMessage;
  selected_skills: BotSkillRun[];
  evidence_records: BotEvidenceRecord[];
  answer: {
    content: string;
    llm_used: boolean;
    risk_flags?: string[];
  };
}

export interface BotKnowledgeFile {
  id: number;
  file_id: string;
  title: string;
  file_name?: string | null;
  content_type?: string | null;
  source_type: string;
  category: string;
  status: string;
  review_status?: string;
  visibility_scope?: string;
  owner_profile_key?: string | null;
  tags?: string[];
  version?: number;
  expires_at?: string | null;
  chunk_count: number;
  uploaded_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotChannelBinding {
  id: number;
  channel_key: string;
  channel_type: string;
  channel_name: string;
  bot_profile_key: string;
  external_id?: string | null;
  binding_config?: Record<string, any>;
  status: string;
  last_seen_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotChannelAdapter {
  id: number;
  adapter_key: string;
  channel_type: string;
  name: string;
  status: string;
  event_mode: string;
  auth_scheme: string;
  signing_required: boolean;
  rate_limit_per_minute: number;
  retry_policy?: Record<string, any>;
  capabilities: string[];
  config?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotInboxItem {
  id: number;
  inbox_id: string;
  conversation_id: string;
  channel_key: string;
  channel_name: string;
  profile_key: string;
  title: string;
  sender_name?: string | null;
  owner_name?: string | null;
  status: string;
  priority: string;
  tags?: string[];
  last_message_at?: string | null;
  handoff_required?: boolean;
  handoff_reason?: string | null;
  resolution_summary?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotHandoff {
  id: number;
  handoff_id: string;
  inbox_id: string;
  conversation_id: string;
  assignee_name: string;
  status: string;
  reason?: string | null;
  requested_by_name?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotAuditLog {
  id: number;
  event_type: string;
  profile_key?: string | null;
  conversation_id?: string | null;
  skill_key?: string | null;
  actor_name?: string | null;
  payload?: Record<string, any>;
  created_at?: string | null;
}

export interface BotBroadcastItem {
  id: number;
  title: string;
  content: string;
  message_type: BotMessageType;
  target_type: string;
  target_summary?: string | null;
  target_payload?: Record<string, any>;
  at_all: boolean;
  status: BotBroadcastStatus;
  created_by?: number | null;
  created_by_name?: string | null;
  sent_by?: number | null;
  sent_by_name?: string | null;
  sent_at?: string | null;
  result_message?: string | null;
  result_payload?: Record<string, any>;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotBroadcastPayload {
  title: string;
  content: string;
  message_type?: BotMessageType;
  target_type?: 'configured_group';
  target_payload?: Record<string, any>;
  at_all?: boolean;
}

export interface BotTask {
  id: number;
  task_id: string;
  title: string;
  task_type: string;
  profile_key: string;
  status: string;
  schedule_type: string;
  schedule_config?: Record<string, any>;
  input_payload?: Record<string, any>;
  result_payload?: Record<string, any>;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotTaskRun {
  id: number;
  run_id: string;
  task_id: string;
  profile_key: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  result_payload?: Record<string, any>;
  error_message?: string | null;
  created_by_name?: string | null;
}

export interface BotActionApproval {
  id: number;
  action_id: string;
  action_type: string;
  title: string;
  profile_key: string;
  status: string;
  payload?: Record<string, any>;
  result_payload?: Record<string, any>;
  requested_by_name?: string | null;
  decided_by_name?: string | null;
  decided_at?: string | null;
  executed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotTestCase {
  id: number;
  name: string;
  profile_key: string;
  input_text: string;
  conversation_turns?: Array<{ role?: string; content?: string }>;
  expected_skills: string[];
  expected_contains: string[];
  required_evidence: boolean;
  priority: string;
  last_result?: Record<string, any>;
  last_run_at?: string | null;
  status: string;
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotEvaluationRun {
  id: number;
  run_id: string;
  test_case_id: number;
  profile_key: string;
  status: string;
  score: number;
  result_payload?: Record<string, any>;
  created_by_name?: string | null;
  created_at?: string | null;
}

export interface BotIntentCorrection {
  id: number;
  phrase: string;
  profile_key?: string | null;
  expected_skills: string[];
  notes?: string | null;
  status: string;
  created_by_name?: string | null;
  created_at?: string | null;
}

export interface BotCollaborationRun {
  id: number;
  run_id: string;
  title: string;
  lead_profile_key: string;
  participant_profiles: string[];
  input_text: string;
  status: string;
  result_payload?: Record<string, any>;
  evidence_records?: BotEvidenceRecord[];
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotQualitySummary {
  test_cases: number;
  failed_evaluation_runs: number;
  pending_actions: number;
  no_evidence_skill_runs: number;
}

export interface BotReleaseVersion {
  id: number;
  version_id: string;
  profile_key: string;
  version: number;
  status: string;
  environment_key: string;
  payload?: Record<string, any>;
  test_summary?: Record<string, any>;
  created_by_name?: string | null;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotFeedback {
  id: number;
  feedback_id: string;
  conversation_id?: string | null;
  message_id?: number | null;
  profile_key?: string | null;
  rating: 'helpful' | 'unhelpful' | 'unsafe' | 'wrong' | string;
  reason?: string | null;
  comment?: string | null;
  status: string;
  created_by_name?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
}

export interface BotKnowledgeSyncJob {
  id: number;
  job_id: string;
  name: string;
  source_type: string;
  category: string;
  status: string;
  schedule_type: string;
  source_config?: Record<string, any>;
  last_run_at?: string | null;
  result_payload?: Record<string, any>;
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotEnvironment {
  id: number;
  environment_key: string;
  name: string;
  status: string;
  is_default: boolean;
  config?: Record<string, any>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotCompliancePolicy {
  id: number;
  policy_key: string;
  name: string;
  policy_type: string;
  status: string;
  action: string;
  rules?: Record<string, any>;
  created_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BotObservabilitySummary {
  range_days: number;
  skill_runs: number;
  failed_skill_runs: number;
  avg_skill_duration_ms: number;
  failed_inbound_events: number;
  open_feedback: number;
}
