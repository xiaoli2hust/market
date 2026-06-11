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
    """爬虫数据：标讯/新闻/竞品/AI资讯。"""

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
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_pushed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
    pushed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_report_pages_type_date", "report_type", "report_date"),
    )


__all__ = [
    "Base",
    "Staff",
    "DailyReportFile",
    "Activity",
    "CrawlerItem",
    "DailyExpress",
    "ReportPage",
]
