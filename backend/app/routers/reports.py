"""报告管理路由。

提供：
- POST /generate  → 生成日报/周报（需 reports:generate）
- GET /           → 报告列表（需 reports:view）
- GET /{id}       → 报告详情（需 reports:view）
- POST /{id}/push → 推送报告到钉钉（需 reports:generate）
- GET /r/{token}  → 公开分享链接（无需认证，直接返回 HTML）
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..database import get_db
from ..models import DepartmentWeeklyReport, ReportPage
from ..services.report_service import generate_daily_report, generate_weekly_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

# 公开分享路由：独立 router，不带 /api 前缀和认证
public_router = APIRouter(tags=["reports-public"])
_PUBLIC_HTML_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
}
MAX_DEPARTMENT_WEEKLY_HTML_BYTES = 8 * 1024 * 1024


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _share_url(report: ReportPage) -> str:
    """构造分享链接相对路径。"""

    return f"/r/{report.access_token}" if report.access_token else ""


def _public_html_response(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content=content, status_code=status_code, headers=_PUBLIC_HTML_HEADERS)


def _report_summary(report: ReportPage) -> dict[str, Any]:
    """报告列表项序列化。"""

    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "share_url": _share_url(report),
        "push_status": report.push_status,
        "version": report.version,
        "status": report.status,
        "note": report.note,
        "pushed_at": report.pushed_at.isoformat() if report.pushed_at else None,
        "superseded_at": report.superseded_at.isoformat() if report.superseded_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text from uploaded weekly HTML without executing it."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag.lower() in {"script", "style", "iframe", "object", "embed"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "iframe", "object", "embed"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", unescape(data)).strip()
        if text:
            self.parts.append(text)


def _department_weekly_summary(row: DepartmentWeeklyReport) -> dict[str, Any]:
    return {
        "id": row.id,
        "department": row.department,
        "week_start": row.week_start.isoformat() if row.week_start else None,
        "week_end": row.week_end.isoformat() if row.week_end else None,
        "title": row.title,
        "file_name": row.file_name,
        "source_type": row.source_type,
        "content_length": row.content_length,
        "uploaded_by": row.uploaded_by,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _extract_html_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()[:200] or None


def _extract_text_content(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return "\n".join(extractor.parts)[:120000]


def _parse_week_start(value: str) -> date:
    try:
        raw = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="周报日期格式应为 YYYY-MM-DD") from exc
    return raw - timedelta(days=raw.weekday())


async def _supersede_peer_reports(db: AsyncSession, report: ReportPage) -> None:
    """Archive other versions for the same report period."""

    rows = (
        await db.execute(
            select(ReportPage).where(
                ReportPage.report_type == report.report_type,
                ReportPage.report_date == report.report_date,
                ReportPage.id != report.id,
                ReportPage.status != "superseded",
            )
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "superseded"
        row.superseded_at = now


# ---------------------------------------------------------------------------
# 1. 生成报告
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_report(
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:generate")),
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
        note = payload.get("note", "").strip() or None
        if report_type == "daily":
            report = await generate_daily_report(db, target_date, note=note)
        else:
            report = await generate_weekly_report(db, target_date, note=note)
    except Exception as exc:
        logger.exception("report generation failed: type=%s date=%s", report_type, target_date)
        raise HTTPException(
            status_code=500,
            detail="报告生成失败，请检查日报数据、日期范围和模型配置后重试",
        ) from exc

    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "date": report.report_date.isoformat() if report.report_date else None,
        "share_url": _share_url(report),
        "version": report.version,
        "status": report.status,
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
    _user: dict = Depends(require_permission("reports:view")),
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
# 3. 部门周报归档
# ---------------------------------------------------------------------------

@router.get("/department-weekly")
async def list_department_weekly_reports(
    department: str | None = Query(None, description="按部门筛选"),
    week_start: str | None = Query(None, description="按周筛选，YYYY-MM-DD，自动归一到周一"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:view")),
) -> dict[str, Any]:
    """部门向公司提交的周报归档列表。"""

    conditions = [DepartmentWeeklyReport.status == "active"]
    if department:
        conditions.append(DepartmentWeeklyReport.department == department.strip())
    if week_start:
        conditions.append(DepartmentWeeklyReport.week_start == _parse_week_start(week_start))

    count_stmt = select(func.count(DepartmentWeeklyReport.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one() or 0

    list_stmt = (
        select(DepartmentWeeklyReport)
        .where(*conditions)
        .order_by(DepartmentWeeklyReport.week_start.desc(), DepartmentWeeklyReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(list_stmt)).scalars().all()
    return {"total": int(total), "items": [_department_weekly_summary(row) for row in rows]}


@router.post("/department-weekly/upload")
async def upload_department_weekly_report(
    week_start: str = Form(...),
    department: str = Form(...),
    title: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("reports:generate")),
) -> dict[str, Any]:
    """上传并归档部门 HTML 周报。"""

    clean_department = department.strip()
    if not clean_department:
        raise HTTPException(status_code=400, detail="请选择或填写部门")

    file_name = file.filename or "department-weekly.html"
    if not file_name.lower().endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="仅支持上传 HTML/HTM 文件")

    raw = await file.read(MAX_DEPARTMENT_WEEKLY_HTML_BYTES + 1)
    if len(raw) > MAX_DEPARTMENT_WEEKLY_HTML_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="HTML 文件不能超过 8MB",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        html = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        html = raw.decode("utf-8", errors="replace")

    normalized_week_start = _parse_week_start(week_start)
    week_end = normalized_week_start + timedelta(days=6)
    clean_title = (title or "").strip() or _extract_html_title(html) or f"{clean_department}周报"

    report = DepartmentWeeklyReport(
        department=clean_department,
        week_start=normalized_week_start,
        week_end=week_end,
        title=clean_title[:200],
        file_name=file_name[:255],
        html_content=html,
        text_content=_extract_text_content(html),
        content_length=len(raw),
        uploaded_by=str(user.get("display_name") or user.get("username") or user.get("sub") or ""),
        status="active",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _department_weekly_summary(report)


@router.get("/department-weekly/{weekly_report_id}")
async def get_department_weekly_report(
    weekly_report_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:view")),
) -> dict[str, Any]:
    """获取部门周报详情，含 HTML 原文和文本摘要素材。"""

    report = (
        await db.execute(
            select(DepartmentWeeklyReport).where(
                DepartmentWeeklyReport.id == weekly_report_id,
                DepartmentWeeklyReport.status == "active",
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="部门周报不存在或已删除")
    return {
        **_department_weekly_summary(report),
        "html_content": report.html_content,
        "text_content": report.text_content,
    }


@router.delete("/department-weekly/{weekly_report_id}")
async def delete_department_weekly_report(
    weekly_report_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:generate")),
) -> dict[str, Any]:
    """软删除部门周报归档。"""

    report = (
        await db.execute(
            select(DepartmentWeeklyReport).where(
                DepartmentWeeklyReport.id == weekly_report_id,
                DepartmentWeeklyReport.status == "active",
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="部门周报不存在或已删除")
    report.status = "deleted"
    await db.commit()
    return {"success": True, "id": weekly_report_id}


# ---------------------------------------------------------------------------
# 4. 报告详情
# ---------------------------------------------------------------------------

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:view")),
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
        "version": report.version,
        "status": report.status,
        "pushed_at": report.pushed_at.isoformat() if report.pushed_at else None,
        "superseded_at": report.superseded_at.isoformat() if report.superseded_at else None,
        "token_expires_at": report.token_expires_at.isoformat() if report.token_expires_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# ---------------------------------------------------------------------------
# 5. 推送报告到钉钉
# ---------------------------------------------------------------------------


@router.post("/{report_id}/push")
async def push_report_to_dingtalk(
    report_id: int,
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("reports:generate")),
) -> dict[str, Any]:
    """推送报告链接到钉钉群。

    发送 Markdown 格式的消息，包含报告摘要和查看链接。
    可选参数：
    - base_url: 平台公网地址前缀（如 https://marketing.example.com），
                用于拼接完整的分享 URL。不传则使用相对路径。
    """
    from ..services import dingtalk_service

    stmt = select(ReportPage).where(ReportPage.id == report_id)
    report = (await db.execute(stmt)).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    share_url = _share_url(report)
    if not share_url:
        raise HTTPException(status_code=400, detail="报告缺少分享 token，无法生成链接")

    base_url = (payload or {}).get("base_url", "").strip()

    # 构造 Markdown 消息
    title, text = dingtalk_service.build_report_markdown(
        report_title=report.title or "营销报告",
        report_type=report.report_type,
        report_date=report.report_date.isoformat() if report.report_date else "",
        share_url=share_url,
        note=report.note,
        base_url=base_url,
    )

    # 发送
    result = await dingtalk_service.send_markdown(db, title, text)

    # 更新推送状态
    if result["success"]:
        report.push_status = "pushed"
        report.status = "published"
        report.pushed_at = datetime.now(timezone.utc)
        await _supersede_peer_reports(db, report)
        await db.flush()

    return {
        "success": result["success"],
        "message": result["message"],
        "push_status": report.push_status,
        "status": report.status,
        "version": report.version,
        "pushed_at": report.pushed_at.isoformat() if report.pushed_at else None,
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
        return _public_html_response(_NOT_FOUND_HTML, status_code=404)

    # 检查过期
    if report.token_expires_at is not None:
        now = datetime.now(timezone.utc)
        expires_at = report.token_expires_at
        # 确保 timezone-aware 比较
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            return _public_html_response(_EXPIRED_HTML, status_code=410)

    # 有效：返回报告 HTML
    html = report.html_content or "<html><body><p>报告内容为空</p></body></html>"
    return _public_html_response(html)
