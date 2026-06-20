"""Express (每日速递) router.

Endpoints:
- POST /express/generate   → Generate express for a date
- GET  /express/            → List all expresses
- GET  /express/{id}        → Express detail with HTML
- POST /express/{id}/push   → Push express to DingTalk (screenshot + message)
- GET  /re/{token}          → Public share link (no auth)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import DailyExpress
from ..services.express_service import generate_daily_express

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/express", tags=["express"])
public_router = APIRouter(tags=["express-public"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _express_summary(express: DailyExpress) -> dict[str, Any]:
    """Serialize express for list view."""

    return {
        "id": express.id,
        "express_date": express.express_date.isoformat() if express.express_date else None,
        "title": express.title,
        "sections": express.sections,
        "push_status": express.push_status,
        "pushed_at": express.pushed_at.isoformat() if express.pushed_at else None,
        "created_at": express.created_at.isoformat() if express.created_at else None,
    }


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_express(
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate daily express for a given date."""

    date_str = payload.get("date", "").strip()
    if not date_str:
        raise HTTPException(status_code=400, detail="date is required (YYYY-MM-DD)")

    try:
        target_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"invalid date: {date_str}")

    try:
        express = await generate_daily_express(db, target_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "id": express.id,
        "express_date": express.express_date.isoformat(),
        "title": express.title,
        "sections": express.sections,
        "created_at": express.created_at.isoformat() if express.created_at else None,
    }


@router.get("/")
async def list_express(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """List all daily expresses, newest first."""

    total = (await db.execute(select(func.count(DailyExpress.id)))).scalar_one() or 0

    stmt = (
        select(DailyExpress)
        .order_by(DailyExpress.express_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "items": [_express_summary(r) for r in rows],
    }


@router.get("/{express_id}")
async def get_express(
    express_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get express detail with HTML content."""

    stmt = select(DailyExpress).where(DailyExpress.id == express_id)
    express = (await db.execute(stmt)).scalar_one_or_none()
    if not express:
        raise HTTPException(status_code=404, detail="express not found")

    return {
        "id": express.id,
        "express_date": express.express_date.isoformat() if express.express_date else None,
        "title": express.title,
        "sections": express.sections,
        "html_content": express.html_content,
        "push_status": express.push_status,
        "pushed_at": express.pushed_at.isoformat() if express.pushed_at else None,
        "created_at": express.created_at.isoformat() if express.created_at else None,
    }


# ---------------------------------------------------------------------------
# Push to DingTalk
# ---------------------------------------------------------------------------


@router.post("/{express_id}/push")
async def push_express_to_dingtalk(
    express_id: int,
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """推送速递到钉钉群。

    流程：
    1. Playwright 将速递 HTML 截图为高清 PNG 长图
    2. 构造 Markdown 消息（含摘要 + 查看链接）
    3. 通过钉钉 Webhook 发送（@所有人）

    可选参数：
    - base_url: 平台公网地址前缀，用于拼接完整链接
    - skip_screenshot: 是否跳过截图（调试用），默认 false
    """
    from ..services import dingtalk_service, screenshot_service

    stmt = select(DailyExpress).where(DailyExpress.id == express_id)
    express = (await db.execute(stmt)).scalar_one_or_none()
    if express is None:
        raise HTTPException(status_code=404, detail="express not found")

    if not express.html_content:
        raise HTTPException(status_code=400, detail="速递内容为空，无法推送")

    base_url = (payload or {}).get("base_url", "").strip()
    skip_screenshot = (payload or {}).get("skip_screenshot", False)

    # Step 1: 截图
    screenshot_path = None
    screenshot_error = None
    if not skip_screenshot:
        try:
            screenshot_path = screenshot_service.get_screenshot_path(express_id)
            if not screenshot_service.screenshot_exists(express_id):
                screenshot_path = await screenshot_service.capture_html_to_image(
                    express.html_content,
                    output_path=screenshot_path,
                    width=390,
                    device_scale_factor=2,
                )
        except Exception as e:
            screenshot_error = str(e)
            logger.warning("速递截图失败，降级为链接推送: %s", e)
            screenshot_path = None

    # Step 2: 构造 Markdown 消息
    title, text = dingtalk_service.build_express_markdown(
        express_title=express.title or "每日速递",
        sections=express.sections or [],
        express_id=express.id,
        base_url=base_url,
    )

    # 附加截图信息
    if screenshot_path and not screenshot_error:
        text += f"\n\n> 📸 长图截图已保存: `{screenshot_path}`"

    # Step 3: 发送
    result = await dingtalk_service.send_markdown(db, title, text, is_at_all=True)

    # 更新推送状态
    if result["success"]:
        express.push_status = "pushed"
        express.pushed_at = datetime.now(timezone.utc)
        await db.flush()

    response: dict[str, Any] = {
        "success": result["success"],
        "message": result["message"],
        "push_status": express.push_status,
        "pushed_at": express.pushed_at.isoformat() if express.pushed_at else None,
    }
    if screenshot_path:
        response["screenshot_path"] = screenshot_path
    if screenshot_error:
        response["screenshot_error"] = screenshot_error

    return response


# ---------------------------------------------------------------------------
# Public share link
# ---------------------------------------------------------------------------


_EXPIRED_HTML = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>链接已过期</title></head>
<body style="font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#f5efe3;">
<div style="background:#fff;padding:40px;border-radius:8px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.1);">
<h2 style="color:#C53A2C;">链接已过期</h2>
<p style="color:#666;">此速递链接已失效。</p>
</div></body></html>
"""


@public_router.get("/re/{express_id}", include_in_schema=False)
async def view_express_public(
    express_id: int,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Public view of a daily express by ID."""

    stmt = select(DailyExpress).where(DailyExpress.id == express_id)
    express = (await db.execute(stmt)).scalar_one_or_none()

    if not express:
        return HTMLResponse(content="<html><body><h2>未找到</h2></body></html>", status_code=404)

    html = express.html_content or "<html><body><p>内容为空</p></body></html>"
    return HTMLResponse(content=html)
