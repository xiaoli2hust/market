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


class PlaceholderResponse(APIBaseModel):
    """路由骨架的占位响应体。"""

    status: str = "not implemented"
    message: str | None = None


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
    extra_data: dict[str, Any] | None = None
    is_pushed: bool
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
    """资讯中心各分类统计。"""

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
    last_run_stats: dict[str, Any] | None = None
    status: str = "idle"  # idle / running / error


class CrawlRunResult(APIBaseModel):
    """手动触发爬取的返回结果。"""

    crawler_name: str
    total_found: int = 0
    new_saved: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    message: str | None = None


__all__ = [
    "APIBaseModel",
    "BaseModel",
    "HealthResponse",
    "PlaceholderResponse",
    "StaffCreate",
    "StaffOut",
    "DailyReportFileOut",
    "ActivityOut",
    "ActivityTypeBucket",
    "StaffActivityBucket",
    "ActivityStats",
    "CrawlerItemOut",
    "ConversationItem",
    "ImportJsonRequest",
    "ImportJsonResponse",
    "LoginRequest",
    "LoginResponse",
]
