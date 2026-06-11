"""报告管理路由。

提供：
- POST /generate  → 生成日报/周报（需 JWT 认证）
- GET /           → 报告列表（需 JWT 认证）
- GET /{id}       → 报告详情（需 JWT 认证）
- GET /r/{token}  → 公开分享链接（无需认证，直接返回 HTML）
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import ReportPage
from ..services.report_service import generate_daily_report, generate_weekly_report

router = APIRouter(prefix="/reports", tags=["reports"])

# 公开分享路由：独立 router，不带 /api 前缀和认证
public_router = APIRouter(tags=["reports-public"])


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _share_url(report: ReportPage) -> str:
    """构造分享链接相对路径。"""

    return f"/r/{report.access_token}" if report.access_token else ""


def _report_summary(report: ReportPage) -> dict[str, Any]:
    """报告列表项序列化。"""

    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "share_url": _share_url(report),
        "push_status": report.push_status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# ---------------------------------------------------------------------------
# 1. 生成报告
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_report(
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """生成日报或周报。

    请求体：
    - report_type: "daily" 或 "weekly"
    - date: 目标日期（daily=那一天，weekly=那周的周一）
    """

    report_type = payload.get("report_type", "").strip().lower()
    date_str = payload.get("date", "").strip()

    if report_type not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="report_type must be 'daily' or 'weekly'")

    try:
        target_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"invalid date: {date_str!r}, expected YYYY-MM-DD",
        )

    try:
        if report_type == "daily":
            report = await generate_daily_report(db, target_date)
        else:
            report = await generate_weekly_report(db, target_date)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"report generation failed: {exc}",
        ) from exc

    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "date": report.report_date.isoformat() if report.report_date else None,
        "share_url": _share_url(report),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# ---------------------------------------------------------------------------
# 2. 报告列表
# ---------------------------------------------------------------------------

@router.get("/")
async def list_reports(
    report_type: str | None = Query(None, description="按类型筛选：daily / weekly"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取报告列表，按创建时间倒序分页。"""

    conditions = []
    if report_type:
        conditions.append(ReportPage.report_type == report_type)

    # 总数
    count_stmt = select(func.count(ReportPage.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    # 列表
    list_stmt = select(ReportPage).order_by(ReportPage.created_at.desc())
    if conditions:
        list_stmt = list_stmt.where(*conditions)
    offset = (page - 1) * page_size
    list_stmt = list_stmt.offset(offset).limit(page_size)

    rows = (await db.execute(list_stmt)).scalars().all()
    items = [_report_summary(r) for r in rows]

    return {"total": int(total), "items": items}


# ---------------------------------------------------------------------------
# 3. 报告详情
# ---------------------------------------------------------------------------

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取报告完整详情，含 html_content 和分享链接。"""

    stmt = select(ReportPage).where(ReportPage.id == report_id)
    report = (await db.execute(stmt)).scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "note": report.note,
        "html_content": report.html_content,
        "access_token": report.access_token,
        "share_url": _share_url(report),
        "push_status": report.push_status,
        "pushed_at": report.pushed_at.isoformat() if report.pushed_at else None,
        "token_expires_at": report.token_expires_at.isoformat() if report.token_expires_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# ---------------------------------------------------------------------------
# 4. 公开分享链接（无需认证）
# ---------------------------------------------------------------------------

_EXPIRED_HTML = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>链接已过期</title>
<style>
  body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }}
  .card {{ background: #fff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,.1); text-align: center; max-width: 400px; }}
  h2 {{ color: #C53030; margin-bottom: 12px; }}
  p {{ color: #666; line-height: 1.6; }}
</style>
</head>
<body>
<div class="card">
  <h2>链接已过期</h2>
  <p>此报告分享链接已失效，请联系管理员获取新链接。</p>
</div>
</body>
</html>
"""

_NOT_FOUND_HTML = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>报告未找到</title>
<style>
  body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }}
  .card {{ background: #fff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,.1); text-align: center; max-width: 400px; }}
  h2 {{ color: #999; margin-bottom: 12px; }}
  p {{ color: #666; line-height: 1.6; }}
</style>
</head>
<body>
<div class="card">
  <h2>报告未找到</h2>
  <p>该链接对应的报告不存在，请检查链接是否正确。</p>
</div>
</body>
</html>
"""


@public_router.get("/r/{token}", include_in_schema=False)
async def view_report_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """公开分享链接：根据 access_token 查看报告 HTML。

    - token 有效且未过期 → 直接渲染 HTML
    - token 过期 → 提示"链接已过期"
    - token 不存在 → 404 页面
    """

    stmt = select(ReportPage).where(ReportPage.access_token == token)
    report = (await db.execute(stmt)).scalar_one_or_none()

    if report is None:
        return HTMLResponse(content=_NOT_FOUND_HTML, status_code=404)

    # 检查过期
    if report.token_expires_at is not None:
        now = datetime.now(timezone.utc)
        expires_at = report.token_expires_at
        # 确保 timezone-aware 比较
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            return HTMLResponse(content=_EXPIRED_HTML, status_code=410)

    # 有效：返回报告 HTML
    html = report.html_content or "<html><body><p>报告内容为空</p></body></html>"
    return HTMLResponse(content=html)
