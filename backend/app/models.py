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
    "CrawlerSource",
    "KeywordConfig",
    "ScheduleConfig",
    "LLMConfig",
    "PromptTemplate",
    "LLMCallLog",
    "SystemUser",
    "OperationLog",
    "APIKeyRecord",
    "DingtalkConfig",
]
