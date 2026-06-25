"""路由聚合入口。

将所有 sub-router 收敛在 ``api_router``，由 ``app.main`` 统一挂载到 ``/api`` 前缀下。
"""

from fastapi import APIRouter

from . import (
    activities,
    auth,
    bidding_express,
    crawler,
    crawler_config,
    dingtalk_robot,
    express,
    import_data,
    llm_config,
    opportunity_leads,
    reports,
    settings,
    staff,
    users,
    users_compat,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(import_data.router)
api_router.include_router(activities.router)
api_router.include_router(staff.router)
api_router.include_router(reports.router)
api_router.include_router(crawler.intelligence_router)
api_router.include_router(crawler.crawler_router)
api_router.include_router(express.router)
api_router.include_router(bidding_express.router)
api_router.include_router(opportunity_leads.router)
api_router.include_router(dingtalk_robot.router)
# 管理中心新增
api_router.include_router(crawler_config.router)
api_router.include_router(llm_config.router)
api_router.include_router(users.router)
api_router.include_router(settings.router)
# 前端兼容：/api/users/* → 复用 staff 逻辑
api_router.include_router(users_compat.router)

__all__ = ["api_router"]
