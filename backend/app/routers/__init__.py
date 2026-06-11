"""路由聚合入口。

将所有 sub-router 收敛在 ``api_router``，由 ``app.main`` 统一挂载到 ``/api`` 前缀下。
"""

from fastapi import APIRouter

from . import activities, auth, import_data, reports, staff, users_compat

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(import_data.router)
api_router.include_router(activities.router)
api_router.include_router(staff.router)
api_router.include_router(reports.router)
# 前端兼容：/api/users/* → 复用 staff 逻辑
api_router.include_router(users_compat.router)

__all__ = ["api_router"]
