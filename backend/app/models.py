"""ORM 模型定义。

所有模型都隶属于 ``marketing`` schema（由 ``Base.metadata`` 统一注入）。
使用 SQLAlchemy 2.0 的 ``Mapped`` 风格声明字段。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Staff(Base):
    """人员表：销售/解决方案/售前。"""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    activities: Mapped[list["Activity"]] = relationship(
        "Activity", back_populates="staff", cascade="all, delete-orphan"
    )


class DailyReportFile(Base):
    """日报原始文件：保留来自机器人的完整 JSON。"""

    __tablename__ = "daily_report_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    user_name: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    raw_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", default="pending"
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    activities: Mapped[list["Activity"]] = relationship(
        "Activity", back_populates="source_file"
    )


class Activity(Base):
    """活动记录：日报解析后的结构化行为数据（核心表）。"""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    opportunity: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0", default=1.0
    )
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    source_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("daily_report_files.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    staff: Mapped["Staff"] = relationship("Staff", back_populates="activities")
    source_file: Mapped[Optional["DailyReportFile"]] = relationship(
        "DailyReportFile", back_populates="activities"
    )

    __table_args__ = (
        Index("ix_activities_staff_date", "staff_id", "report_date"),
    )


class CrawlerItem(Base):
    """爬虫数据：标讯雷达/政策研判/市场线索/竞品/行业知识。"""

    __tablename__ = "crawler_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    published_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount_wan: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    buyer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notice_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    matched_keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_pushed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    is_invalid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False, index=True
    )
    invalid_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_crawler_items_category_amount", "category", "amount_wan"),
        Index("ix_crawler_items_category_region", "category", "region"),
        Index("ix_crawler_items_category_notice", "category", "notice_type"),
    )


class CrawlerRunLog(Base):
    """爬虫运行日志：记录每次采集的统计、耗时与失败原因。"""

    __tablename__ = "crawler_run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    new_saved: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    low_score_discarded: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_crawler_run_logs_name_created", "crawler_name", "created_at"),
        Index("ix_crawler_run_logs_category_created", "category", "created_at"),
    )


class EvidenceRecord(Base):
    """证据记录：Agent 结论、金额、客户和风险判断的可追溯来源。"""

    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    query_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0", default=1.0
    )
    data_quality_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    event_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_evidence_records_record", "record_type", "record_id"),
        Index("ix_evidence_records_category_time", "category", "collected_at"),
    )


class IntelligenceEvent(Base):
    """情报事件：解释外部情报如何形成判断、线索或后续动作。"""

    __tablename__ = "intelligence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    crawler_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("crawler_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    opportunity_lead_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunity_leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    event_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_intelligence_events_category_created", "category", "created_at"),
        Index("ix_intelligence_events_type_created", "event_type", "created_at"),
    )


class CrawlerTaskLock(Base):
    """爬虫任务锁：防止多实例或重复点击导致同一爬虫并发运行。"""

    __tablename__ = "crawler_task_locks"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    lock_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrawlerTaskRun(Base):
    """爬虫任务运行实例：记录调度/手动触发、锁归属和最终状态。"""

    __tablename__ = "crawler_task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    crawler_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    trigger_source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    lock_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_crawler_task_runs_name_created", "crawler_name", "created_at"),
        Index("ix_crawler_task_runs_status_created", "status", "created_at"),
    )


class OpportunityLead(Base):
    """G端商机线索：从公开采购公告中识别出的可行动销售线索。"""

    __tablename__ = "opportunity_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    buyer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    budget: Mapped[float] = mapped_column(Float, nullable=False, server_default="0", default=0.0)
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommended_action: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, server_default="bidding", default="bidding")
    source_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    procurement_method: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    publish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="new", default="new", index=True)
    raw_record: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_opportunity_leads_decision_score", "decision", "score"),
        Index("ix_opportunity_leads_status_score", "status", "score"),
    )


class DailyExpress(Base):
    """每日速递：聚合后的多板块内容与推送状态。"""

    __tablename__ = "daily_express"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    express_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sections: Mapped[list] = mapped_column(JSON, nullable=False)
    html_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dingtalk_media_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    push_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", default="pending"
    )
    pushed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReportPage(Base):
    """报告页面：日报/周报渲染结果与领导查看链接。"""

    __tablename__ = "report_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True
    )
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    push_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft", default="draft"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", default=1
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft", default="draft"
    )
    pushed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_report_pages_type_date", "report_type", "report_date"),
        Index("ix_report_pages_type_date_status", "report_type", "report_date", "status"),
    )


class DepartmentWeeklyReport(Base):
    """部门周报归档：保存部门向公司提交的 HTML 周报原文。"""

    __tablename__ = "department_weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="html_upload", default="html_upload"
    )
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_department_weekly_reports_week_department", "week_start", "department"),
        Index("ix_department_weekly_reports_status_created", "status", "created_at"),
    )


# ---------------------------------------------------------------------------
# 管理中心新增模型
# ---------------------------------------------------------------------------


class CrawlerSource(Base):
    """爬虫目标站点配置。"""

    __tablename__ = "crawler_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    selectors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    runtime_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending", default="pending"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_diagnosis_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    last_diagnosis_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_cursor: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    last_saved: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KeywordConfig(Base):
    """关键词配置（按分类存储）。"""

    __tablename__ = "keyword_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ScheduleConfig(Base):
    """爬虫调度配置（单行记录）。"""

    __tablename__ = "schedule_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawl_frequency_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="2", default=2
    )
    relevance_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="30", default=30.0
    )
    auto_crawl_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LLMConfig(Base):
    """大模型全局配置。"""

    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="deepseek-chat")
    api_base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="https://api.deepseek.com"
    )
    api_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    default_temperature: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.2", default=0.2
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PromptTemplate(Base):
    """Prompt 模板（按场景存储）。"""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.2", default=0.2
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="2000", default=2000
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LLMCallLog(Base):
    """大模型调用审计：只记录调用事实，不保存完整提示词与密钥。"""

    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_llm_call_logs_scene_created", "scene", "created_at"),
        Index("ix_llm_call_logs_status_created", "status", "created_at"),
    )


class SystemUser(Base):
    """系统用户（管理员账号）。"""

    __tablename__ = "system_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="viewer")
    display_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OperationLog(Base):
    """操作日志。"""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BotBroadcast(Base):
    """机器人群发记录：保存人工群发、自动推送和失败重试的完整结果。"""

    __tablename__ = "bot_broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="markdown", default="markdown"
    )
    target_type: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="configured_group", default="configured_group"
    )
    target_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    at_all: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft", default="draft", index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sent_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sent_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_broadcasts_status_created", "status", "created_at"),
        Index("ix_bot_broadcasts_target_created", "target_type", "created_at"),
    )


class BotProfile(Base):
    """机器人定义：描述一个可运行 Agent 的身份、边界和默认 Skill。"""

    __tablename__ = "bot_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="enabled", default="enabled", index=True)
    allowed_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotSkill(Base):
    """Skill 契约：机器人可调用能力包，包含输入输出、证据和权限规则。"""

    __tablename__ = "bot_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_scenarios: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    input_contract: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_contract: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_permission: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    implementation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="implemented", default="implemented"
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotConversation(Base):
    """机器人会话：对话测试台和未来群聊入口共用的会话容器。"""

    __tablename__ = "bot_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    simulated_user_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    channel_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="test_console", default="test_console", index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active", index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["BotMessage"]] = relationship(
        "BotMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_bot_conversations_profile_created", "profile_key", "created_at"),
    )


class BotMessage(Base):
    """机器人消息：保存用户输入、机器人回复和系统过程消息。"""

    __tablename__ = "bot_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_pk: Mapped[int] = mapped_column(
        ForeignKey("bot_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="text", default="text")
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    conversation: Mapped["BotConversation"] = relationship("BotConversation", back_populates="messages")

    __table_args__ = (
        Index("ix_bot_messages_conversation_created", "conversation_pk", "created_at"),
    )


class BotSkillRun(Base):
    """Skill 运行记录：每次 Agent 调用 Skill 的输入、输出、证据和错误。"""

    __tablename__ = "bot_skill_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    conversation_pk: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bot_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bot_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    evidence_records: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_bot_skill_runs_skill_created", "skill_key", "created_at"),
        Index("ix_bot_skill_runs_profile_created", "profile_key", "created_at"),
    )


class BotToolCall(Base):
    """工具调用记录：Skill 内部访问数据库、知识、外部接口等步骤。"""

    __tablename__ = "bot_tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_run_id: Mapped[int] = mapped_column(
        ForeignKey("bot_skill_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BotKnowledgeFile(Base):
    """知识空间文件：机器人可检索材料的原文与解析状态。"""

    __tablename__ = "bot_knowledge_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="manual_upload", default="manual_upload")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="indexed", default="indexed", index=True)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="approved", default="approved", index=True)
    visibility_scope: Mapped[str] = mapped_column(String(40), nullable=False, server_default="all_bots", default="all_bots", index=True)
    owner_profile_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["BotKnowledgeChunk"]] = relationship(
        "BotKnowledgeChunk", back_populates="file", cascade="all, delete-orphan"
    )


class BotKnowledgeChunk(Base):
    """知识切片：用于可追溯检索。当前版本使用关键词检索，后续可替换向量索引。"""

    __tablename__ = "bot_knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_pk: Mapped[int] = mapped_column(
        ForeignKey("bot_knowledge_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    file: Mapped["BotKnowledgeFile"] = relationship("BotKnowledgeFile", back_populates="chunks")

    __table_args__ = (
        Index("ix_bot_knowledge_chunks_file_index", "file_pk", "chunk_index"),
    )


class BotChannelBinding(Base):
    """群聊接入绑定：描述外部群和机器人 Profile 的绑定关系。"""

    __tablename__ = "bot_channel_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bot_profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    binding_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active", index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotChannelAdapter(Base):
    """渠道适配器：管理钉钉/飞书/企微/Slack/Teams 等接入能力和安全策略。"""

    __tablename__ = "bot_channel_adapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adapter_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="enabled", default="enabled", index=True)
    event_mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="webhook", default="webhook")
    auth_scheme: Mapped[str] = mapped_column(String(40), nullable=False, server_default="signed_webhook", default="signed_webhook")
    signing_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60", default=60)
    retry_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_channel_adapters_type_status", "channel_type", "status"),
    )


class BotInboundEvent(Base):
    """入站消息事件：用于签名校验、去重、限流、失败重试和审计追踪。"""

    __tablename__ = "bot_inbound_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    channel_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    sender_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_bot_inbound_events_channel_received", "channel_key", "received_at"),
        Index("ix_bot_inbound_events_status_received", "status", "received_at"),
    )


class BotInboxItem(Base):
    """群聊机器人收件箱：把真实群消息沉淀为可处理、可接管、可复盘的工作项。"""

    __tablename__ = "bot_inbox_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inbox_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    conversation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open", default="open", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="P2", default="P2", index=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    handoff_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    handoff_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_inbox_items_status_priority", "status", "priority"),
        Index("ix_bot_inbox_items_channel_status", "channel_key", "status"),
    )


class BotHandoff(Base):
    """人工接管：机器人无法独立完成时转交负责人处理。"""

    __tablename__ = "bot_handoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    handoff_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    inbox_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    assignee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open", default="open", index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotTestCase(Base):
    """机器人测试用例：把高频问题固化成验收资产。"""

    __tablename__ = "bot_test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_turns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expected_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expected_contains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="P1", default="P1", index=True)
    last_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active")
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotAuditLog(Base):
    """机器人审计：记录对话、配置、Skill 和外部动作的关键事件。"""

    __tablename__ = "bot_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    profile_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    skill_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class BotTask(Base):
    """机器人任务：定时、手动或外部触发的 Agent 工作单。"""

    __tablename__ = "bot_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="enabled", default="enabled", index=True)
    schedule_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual", default="manual")
    schedule_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_tasks_profile_status", "profile_key", "status"),
        Index("ix_bot_tasks_type_status", "task_type", "status"),
    )


class BotTaskRun(Base):
    """机器人任务运行记录：每次调度/手动运行都有结果、耗时和错误。"""

    __tablename__ = "bot_task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual", default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_bot_task_runs_task_started", "task_id", "started_at"),
        Index("ix_bot_task_runs_status_started", "status", "started_at"),
    )


class BotActionApproval(Base):
    """机器人外部动作审批：群发、提醒、数据变更等动作先审批再执行。"""

    __tablename__ = "bot_action_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    profile_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", default="pending", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    requested_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decided_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_action_approvals_status_created", "status", "created_at"),
    )


class BotEvaluationRun(Base):
    """机器人评测结果：记录测试用例每次运行是否达标。"""

    __tablename__ = "bot_evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    test_case_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bot_test_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0", default=0)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_bot_evaluation_runs_profile_created", "profile_key", "created_at"),
        Index("ix_bot_evaluation_runs_status_created", "status", "created_at"),
    )


class BotIntentCorrection(Base):
    """意图纠错：把人工纠正沉淀为后续 Skill 路由参考。"""

    __tablename__ = "bot_intent_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phrase: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    profile_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    expected_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", default="active", index=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class BotCollaborationRun(Base):
    """多机器人协作：一个问题由多个 Profile 分工回答后汇总。"""

    __tablename__ = "bot_collaboration_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    lead_profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    participant_profiles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_records: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotReleaseVersion(Base):
    """机器人发布版本：Profile/Skill/Prompt/知识策略从草稿到发布可追溯。"""

    __tablename__ = "bot_release_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    profile_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft", default="draft", index=True)
    environment_key: Mapped[str] = mapped_column(String(40), nullable=False, server_default="prod", default="prod", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    test_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bot_release_versions_profile_version", "profile_key", "version"),
        Index("ix_bot_release_versions_env_status", "environment_key", "status"),
    )


class BotFeedback(Base):
    """用户反馈：把好/坏答案转成可处理的质量闭环。"""

    __tablename__ = "bot_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    profile_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    rating: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open", default="open", index=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class BotKnowledgeSyncJob(Base):
    """知识同步任务：统一管理周报、文档库、网页资料等知识来源。"""

    __tablename__ = "bot_knowledge_sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="enabled", default="enabled", index=True)
    schedule_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual", default="manual")
    source_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotEnvironment(Base):
    """机器人运行环境：区分测试、预发布和生产，支持版本治理。"""

    __tablename__ = "bot_environments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    environment_key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="enabled", default="enabled", index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BotCompliancePolicy(Base):
    """机器人合规策略：敏感词、PII、动作确认和数据保留规则。"""

    __tablename__ = "bot_compliance_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="enabled", default="enabled", index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, server_default="warn", default="warn")
    rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class APIKeyRecord(Base):
    """API Key 管理。"""

    __tablename__ = "api_key_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    key_value: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DingtalkConfig(Base):
    """钉钉配置。"""

    __tablename__ = "dingtalk_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    secret: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    # 企业内部应用凭证（用于图片上传 / 长图推送）
    app_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    app_secret: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    app_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    robot_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    open_conversation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cool_app_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 结构化标讯账号
    jianyu_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jianyu_password: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    jianyu_api_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


__all__ = [
    "Base",
    "Staff",
    "DailyReportFile",
    "Activity",
    "CrawlerItem",
    "EvidenceRecord",
    "IntelligenceEvent",
    "CrawlerTaskLock",
    "CrawlerTaskRun",
    "OpportunityLead",
    "DailyExpress",
    "ReportPage",
    "DepartmentWeeklyReport",
    "CrawlerSource",
    "KeywordConfig",
    "ScheduleConfig",
    "LLMConfig",
    "PromptTemplate",
    "LLMCallLog",
    "SystemUser",
    "OperationLog",
    "BotBroadcast",
    "BotProfile",
    "BotSkill",
    "BotConversation",
    "BotMessage",
    "BotSkillRun",
    "BotToolCall",
    "BotKnowledgeFile",
    "BotKnowledgeChunk",
    "BotChannelBinding",
    "BotChannelAdapter",
    "BotInboundEvent",
    "BotInboxItem",
    "BotHandoff",
    "BotTestCase",
    "BotAuditLog",
    "BotTask",
    "BotTaskRun",
    "BotActionApproval",
    "BotEvaluationRun",
    "BotIntentCorrection",
    "BotCollaborationRun",
    "BotReleaseVersion",
    "BotFeedback",
    "BotKnowledgeSyncJob",
    "BotEnvironment",
    "BotCompliancePolicy",
    "APIKeyRecord",
    "DingtalkConfig",
]
