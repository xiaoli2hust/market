"""前端兼容路由：/api/users/* → 委托到 staff 逻辑。

前端 api.ts 中部分接口使用 /api/users/ 路径（如 fetchStaff、fetchDepartments），
后端实际模型为 staff，此处做路径适配，避免前端改动。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from .staff import get_departments, get_staff_detail, list_staff

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
@router.get("/")
async def users_list(
    is_active: bool | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """兼容接口：等价 GET /api/staff/。"""

    return await list_staff(is_active=is_active, department=department, db=db)


@router.get("/departments")
async def users_departments(db: AsyncSession = Depends(get_db)) -> list[str]:
    """兼容接口：等价 GET /api/staff/departments。"""

    return await get_departments(db=db)


@router.get("/{user_id}")
async def users_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """兼容接口：等价 GET /api/staff/{staff_id}。"""

    return await get_staff_detail(staff_id=user_id, db=db)
