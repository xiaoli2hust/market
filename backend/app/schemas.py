"""Pydantic Schemas。

围绕 6 张核心表与对外接口定义请求/响应模型，
统一继承 ``APIBaseModel`` 以启用 ``from_attributes=True``。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIBaseModel(BaseModel):
    """全局 Pydantic 基类。

    - ``from_attributes=True`` 允许直接从 ORM 对象构造响应模型；
    - ``populate_by_name=True`` 允许使用字段别名进行兼容。
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class HealthResponse(APIBaseModel):
    """健康检查响应。"""

    status: str = "ok"
    version: str | None = None


# ---------- Staff -------------------------------------------------------------


class StaffCreate(APIBaseModel):
    """新增/更新人员的请求体。"""

    name: str = Field(..., max_length=50)
    role: str = Field(..., max_length=20, description="销售/解决方案/售前")
    department: str = Field(..., max_length=50, description="华北组/华东组/行业组")
    is_active: bool = True


class StaffOut(APIBaseModel):
    """人员对外响应。"""

    id: int
    name: str
    role: str
    department: str
    is_active: bool
    created_at: datetime


# ---------- DailyReportFile ---------------------------------------------------


class DailyReportFileOut(APIBaseModel):
    """日报原始文件对外响应。"""

    id: int
    user_id: str
    user_name: str
    file_name: str
    file_date: date
    parse_status: str
    parsed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


# ---------- Activity ----------------------------------------------------------


class ActivityOut(APIBaseModel):
    """活动记录对外响应（扁平化 staff_name 便于前端列表展示）。"""

    id: int
    staff_id: int
    staff_name: str | None = None
    report_date: date
    activity_type: str
    target: str | None = None
    opportunity: str | None = None
    opportunity_id: str | None = None
    description: str | None = None
    confidence: float
    is_reviewed: bool
    source_file_id: int | None = None
    created_at: datetime


class ActivityTypeBucket(APIBaseModel):
    """按行为标签维度的统计桶。"""

    activity_type: str
    count: int


class StaffActivityBucket(APIBaseModel):
    """按人员维度的统计桶。"""

    staff_id: int
    staff_name: str
    count: int


class ActivityStats(APIBaseModel):
    """活动统计聚合返回。"""

    total: int = 0
    reviewed: int = 0
    unreviewed: int = 0
    by_type: list[ActivityTypeBucket] = Field(default_factory=list)
    by_staff: list[StaffActivityBucket] = Field(default_factory=list)
    by_department: dict[str, int] = Field(default_factory=dict)


# ---------- CrawlerItem -------------------------------------------------------


class CrawlerItemOut(APIBaseModel):
    """爬虫数据对外响应。"""

    id: int
    category: str
    title: str
    content: str | None = None
    summary: str | None = None
    source: str | None = None
    source_url: str | None = None
    published_at: date | None = None
    relevance_score: float | None = None
    amount_wan: float | None = None
    buyer: str | None = None
    region: str | None = None
    notice_type: str | None = None
    matched_keywords: list[str] | None = None
    extra_data: dict[str, Any] | None = None
    is_pushed: bool
    is_invalid: bool = False
    invalid_reason: str | None = None
    created_at: datetime


# ---------- Import JSON --------------------------------------------------------


class ConversationItem(APIBaseModel):
    """机器人推送的单条聊天问答。"""

    time: str = ""
    question: str = ""
    answer: str = ""


class ImportJsonRequest(APIBaseModel):
    """JSON 上传请求体。

    与内网机器人推送的聊天记录 JSON 一一对应：
    ``conversations`` 中的 ``question`` 字段即日报原文，
    服务端会拼接后送 LLM 抽取活动。
    """

    user_id: str = Field(..., max_length=50)
    user_name: str = Field(..., max_length=50)
    date: str = Field(..., description="日报日期，如 2026-06-04")
    timezone: str = "Asia/Shanghai"
    created_at: str = ""
    last_updated: str = ""
    conversation_count: int = 0
    conversations: list[ConversationItem] = Field(default_factory=list)


class ImportJsonResponse(APIBaseModel):
    """JSON 上传响应：返回新文件 ID 与解析队列状态。"""

    file_id: int
    parse_status: str = "pending"
    activities_count: int = 0
    message: str | None = None


# ---------- Auth --------------------------------------------------------------


class LoginRequest(APIBaseModel):
    """登录请求体。"""

    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)


class LoginResponse(APIBaseModel):
    """登录响应：JWT token + 过期时间。"""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None


# ---------- Intelligence / Crawler -------------------------------------------


class IntelligenceStats(APIBaseModel):
    """市场洞察各分类统计。"""

    total: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    today_count: int = 0
    latest_crawl: dict[str, datetime | None] = Field(default_factory=dict)


class CrawlerStatusOut(APIBaseModel):
    """单个爬虫的运行状态。"""

    name: str
    category: str
    label: str
    total_collected: int = 0
    last_run_at: datetime | None = None
    last_item_at: datetime | None = None
    last_run_stats: dict[str, Any] | None = None
    active_sources: int = 0
    last_error: str | None = None
    status: str = "idle"  # idle / running / error


class CrawlRunResult(APIBaseModel):
    """手动触发爬取的返回结果。"""

    crawler_name: str
    total_found: int = 0
    new_saved: int = 0
    duplicates_skipped: int = 0
    low_score_discarded: int = 0
    errors: int = 0
    duration_ms: int | None = None
    message: str | None = None


class CrawlerRunLogOut(APIBaseModel):
    """爬虫运行日志。"""

    id: int
    crawler_name: str
    category: str
    status: str
    total_found: int = 0
    new_saved: int = 0
    duplicates_skipped: int = 0
    low_score_discarded: int = 0
    errors: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime


__all__ = [
    "APIBaseModel",
    "BaseModel",
    "HealthResponse",
    "StaffCreate",
    "StaffOut",
    "DailyReportFileOut",
    "ActivityOut",
    "ActivityTypeBucket",
    "StaffActivityBucket",
    "ActivityStats",
    "CrawlerItemOut",
    "CrawlerRunLogOut",
    "ConversationItem",
    "ImportJsonRequest",
    "ImportJsonResponse",
    "LoginRequest",
    "LoginResponse",
    # Bot schemas
    "BotProfileRequest",
    "BotSkillUpdateRequest",
    "BotChatTestRequest",
    "BotKnowledgeTextRequest",
    "BotKnowledgeUpdateRequest",
    "BotKnowledgeSearchRequest",
    "BotInboundTestRequest",
    "BotChannelAdapterRequest",
    "BotChannelBindingCreateRequest",
    "BotChannelBindingUpdateRequest",
    "BotInboxUpdateRequest",
    "BotHandoffRequest",
    "BotTaskRequest",
    "BotApprovalRequest",
    "BotTestCaseRequest",
    "BotIntentCorrectionRequest",
    "BotCollaborationRequest",
    "BotReleaseRequest",
    "BotFeedbackRequest",
    "BotKnowledgeSyncRequest",
    "BotCompliancePolicyRequest",
    "BroadcastRequest",
]


# ---------- Bot Center -------------------------------------------------------


class BotProfileRequest(APIBaseModel):
    """创建/更新机器人 Profile。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="allow")

    name: str = ""
    profile_key: str = ""
    description: str = ""
    system_prompt: str = ""
    default_role: str = ""
    status: str = ""
    allowed_skills: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class BotSkillUpdateRequest(APIBaseModel):
    """更新 Skill 配置。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    enabled: bool | None = None
    config: dict[str, Any] | None = None
    trigger_scenarios: list[str] | None = None
    evidence_rules: dict[str, Any] | None = None
    input_contract: dict[str, Any] | None = None
    output_contract: dict[str, Any] | None = None


class BotChatTestRequest(APIBaseModel):
    """对话测试台请求。"""

    profile_key: str = "management_assistant_agent"
    conversation_id: str | None = None
    simulated_user_role: str | None = None
    message: str = ""


class BotKnowledgeTextRequest(APIBaseModel):
    """保存文本到知识空间。"""

    title: str = ""
    text_content: str = ""
    category: str = "general"
    owner_profile_key: str | None = None
    visibility_scope: str = "all_bots"
    tags: list[str] = Field(default_factory=list)
    review_status: str = "approved"


class BotKnowledgeUpdateRequest(APIBaseModel):
    """更新知识文件元数据。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    status: str | None = None
    visibility_scope: str | None = None
    tags: list[str] | None = None
    review_status: str | None = None


class BotKnowledgeSearchRequest(APIBaseModel):
    """知识检索请求。"""

    query: str = ""


class BotInboundTestRequest(APIBaseModel):
    """模拟入站消息。"""

    channel_key: str = "dingtalk_default"
    content: str = ""
    sender_id: str | None = None
    sender_name: str | None = None


class BotChannelAdapterRequest(APIBaseModel):
    """新增/更新渠道适配器。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    adapter_key: str = ""
    channel_type: str = ""
    name: str = ""
    auth_config: dict[str, Any] = Field(default_factory=dict)
    rate_limit: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class BotChannelBindingCreateRequest(APIBaseModel):
    """新增群聊绑定。"""

    channel_key: str = ""
    channel_type: str = "dingtalk"
    channel_name: str = "未命名群聊"
    bot_profile_key: str = "management_assistant_agent"
    external_id: str = ""
    binding_config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class BotChannelBindingUpdateRequest(APIBaseModel):
    """更新群聊绑定。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    channel_name: str | None = None
    channel_type: str | None = None
    bot_profile_key: str | None = None
    external_id: str | None = None
    status: str | None = None
    binding_config: dict[str, Any] | None = None


class BotInboxUpdateRequest(APIBaseModel):
    """更新收件箱条目。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    status: str | None = None
    assignee: str | None = None
    priority: str | None = None
    conclusion: str | None = None


class BotHandoffRequest(APIBaseModel):
    """人工接管请求。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    assignee: str = ""
    reason: str = ""
    priority: str = "normal"


class BotTaskRequest(APIBaseModel):
    """创建自动任务。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    title: str = ""
    task_type: str = ""
    profile_key: str = ""
    schedule_type: str = ""
    schedule_config: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)


class BotApprovalRequest(APIBaseModel):
    """创建审批请求。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    action_type: str = ""
    title: str = ""
    profile_key: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class BotTestCaseRequest(APIBaseModel):
    """创建测试用例。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    name: str = ""
    profile_key: str = ""
    input_text: str = ""
    expected_skills: list[str] = Field(default_factory=list)
    expected_contains: list[str] = Field(default_factory=list)
    required_evidence: str | None = None
    priority: str = "normal"


class BotIntentCorrectionRequest(APIBaseModel):
    """创建意图纠正。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    phrase: str = ""
    profile_key: str = ""
    expected_skills: list[str] = Field(default_factory=list)
    notes: str = ""


class BotCollaborationRequest(APIBaseModel):
    """创建协作运行。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    title: str = ""
    lead_profile_key: str = ""
    participant_profiles: list[str] = Field(default_factory=list)
    input_text: str = ""


class BotReleaseRequest(APIBaseModel):
    """创建发布版本。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    profile_key: str = ""
    description: str = ""
    changelog: str = ""


class BotFeedbackRequest(APIBaseModel):
    """记录用户反馈。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    conversation_id: str = ""
    message_id: str = ""
    rating: str = ""
    comment: str = ""
    category: str = ""


class BotKnowledgeSyncRequest(APIBaseModel):
    """创建知识同步任务。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    source_type: str = ""
    source_config: dict[str, Any] = Field(default_factory=dict)
    target_category: str = "general"
    schedule: str = "manual"


class BotCompliancePolicyRequest(APIBaseModel):
    """新增/更新合规策略。"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    policy_key: str = ""
    name: str = ""
    description: str = ""
    retention_days: int = 90
    content_filters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class BroadcastRequest(APIBaseModel):
    """群发消息请求。"""

    title: str = ""
    content: str = ""
    message_type: str = "markdown"
    target_type: str = ""
    target_payload: dict[str, Any] | None = None
    at_all: bool = False
