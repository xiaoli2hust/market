"""人员管理路由。

实现人员列表、部门字典、个人详情（近期活动 + 关键指标）等接口，
对应前端「人员视角」页面与抽屉详情。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Activity, Staff

router = APIRouter(prefix="/staff", tags=["staff"])


def _staff_to_dict(staff: Staff) -> dict[str, Any]:
    """统一的人员序列化。"""

    return {
        "id": staff.id,
        "name": staff.name,
        "role": staff.role,
        "department": staff.department,
        "is_active": staff.is_active,
        "created_at": staff.created_at.isoformat() if staff.created_at else None,
    }


def _activity_to_dict(activity: Activity, staff: Staff | None) -> dict[str, Any]:
    """活动记录序列化（与 activities 路由保持字段一致，含前端兼容别名）。"""

    report_date_str = activity.report_date.isoformat() if activity.report_date else None
    return {
        "id": activity.id,
        "staff_id": activity.staff_id,
        "user_id": activity.staff_id,
        "staff_name": staff.name if staff else None,
        "user_name": staff.name if staff else None,
        "department": staff.department if staff else None,
        "user_department": staff.department if staff else None,
        "report_date": report_date_str,
        "activity_date": report_date_str,
        "activity_type": activity.activity_type,
        "action_type": activity.activity_type,
        "action_type_label": activity.activity_type,
        "target": activity.target,
        "customer_name": activity.target,
        "opportunity": activity.opportunity,
        "opportunity_name": activity.opportunity,
        "opportunity_id": activity.opportunity_id,
        "description": activity.description,
        "summary": activity.description,
        "detail": activity.description,
        "confidence": activity.confidence,
        "is_reviewed": activity.is_reviewed,
        "source_file_id": activity.source_file_id,
        "source": "daily_report",
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


@router.get("")
@router.get("/")
async def list_staff(
    is_active: bool | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """获取人员列表，可按启用状态/部门筛选。"""

    stmt = select(Staff)
    if is_active is not None:
        stmt = stmt.where(Staff.is_active.is_(is_active))
    if department:
        stmt = stmt.where(Staff.department == department)
    stmt = stmt.order_by(Staff.department.asc(), Staff.id.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_staff_to_dict(s) for s in rows]


@router.get("/departments")
async def get_departments(db: AsyncSession = Depends(get_db)) -> list[str]:
    """获取所有部门（去重）。"""

    stmt = (
        select(distinct(Staff.department))
        .where(Staff.department.isnot(None))
        .order_by(Staff.department.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [row[0] for row in rows if row[0]]


@router.get("/{staff_id}")
async def get_staff_detail(
    staff_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取个人详情：基础信息 + 近 30 天关键指标 + 最近 20 条活动。"""

    staff = (
        await db.execute(select(Staff).where(Staff.id == staff_id))
    ).scalar_one_or_none()
    if staff is None:
        raise HTTPException(status_code=404, detail=f"staff {staff_id} not found")

    today = date.today()
    window_start = today - timedelta(days=29)  # 近 30 天含今天

    base_window = [
        Activity.staff_id == staff_id,
        Activity.report_date >= window_start,
        Activity.report_date <= today,
    ]

    # 总活动数
    total_stmt = select(func.count(Activity.id)).where(*base_window)
    total_activities = (await db.execute(total_stmt)).scalar_one() or 0

    # 活跃天数
    active_days_stmt = (
        select(func.count(distinct(Activity.report_date))).where(*base_window)
    )
    active_days = (await db.execute(active_days_stmt)).scalar_one() or 0

    # 拜访客户次数
    visit_stmt = select(func.count(Activity.id)).where(
        *base_window, Activity.activity_type == "拜访客户"
    )
    visit_count = (await db.execute(visit_stmt)).scalar_one() or 0

    # 跟进的不重复商机数（不限时间窗口，反映该人的覆盖面）
    opportunity_stmt = select(
        func.count(
            distinct(func.coalesce(Activity.opportunity_id, Activity.opportunity))
        )
    ).where(
        Activity.staff_id == staff_id,
        (Activity.opportunity_id.isnot(None)) | (Activity.opportunity.isnot(None)),
    )
    opportunity_count = (await db.execute(opportunity_stmt)).scalar_one() or 0

    # 最近 20 条活动
    recent_stmt = (
        select(Activity)
        .where(Activity.staff_id == staff_id)
        .order_by(Activity.report_date.desc(), Activity.id.desc())
        .limit(20)
    )
    recent_rows = (await db.execute(recent_stmt)).scalars().all()
    recent_activities = [_activity_to_dict(a, staff) for a in recent_rows]

    return {
        "staff": _staff_to_dict(staff),
        "stats": {
            "active_days": int(active_days),
            "visit_count": int(visit_count),
            "opportunity_count": int(opportunity_count),
            "total_activities": int(total_activities),
        },
        "recent_activities": recent_activities,
    }
