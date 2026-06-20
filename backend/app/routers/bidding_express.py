"""标讯速递路由。

- POST /bidding-express/generate  → 生成标讯速递 HTML
- GET  /bidding-express/latest    → 获取最新标讯速递
- POST /bidding-express/push      → 推送到钉钉
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import DingtalkConfig
from ..services import dingtalk_service
from ..services.bidding_express_service import build_express, render_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bidding-express", tags=["bidding-express"])

# 缓存最新生成的速递
_latest_express: dict[str, Any] = {}


def _get_api_key(db) -> str:
    """获取剑鱼 API key。"""
    # 优先从数据库读取
    import sqlite3
    conn = sqlite3.connect("market.db")
    row = conn.execute("SELECT jianyu_password FROM dingtalk_configs LIMIT 1").fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    raise HTTPException(400, "剑鱼 API Key 未配置，请在管理中心 → 接口与密钥 → 剑鱼标讯配置中填写")


@router.post("/generate")
async def generate_bidding_express(
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """生成标讯速递。"""
    api_key = _get_api_key(db)
    express_date = (payload or {}).get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    express = build_express(api_key, express_date)
    html = render_html(express)

    # 缓存
    _latest_express["html"] = html
    _latest_express["date"] = express_date
    _latest_express["total"] = express.total
    _latest_express["groups"] = [
        {"subtype": g.subtype, "label": g.label, "count": len(g.items)}
        for g in express.groups
    ]
    _latest_express["high_value_count"] = len(express.high_value_items)
    _latest_express["priority_count"] = len(express.priority_items)

    return {
        "express_date": express_date,
        "total": express.total,
        "groups": _latest_express["groups"],
        "high_value_count": len(express.high_value_items),
        "priority_count": len(express.priority_items),
        "message": f"生成成功：{express.total} 条标讯，{len(express.groups)} 个分组",
    }


@router.get("/latest")
async def get_latest_express(
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取最新标讯速递概要。"""
    if not _latest_express:
        return {"status": "empty", "message": "尚未生成标讯速递"}
    return {
        "status": "ok",
        "express_date": _latest_express.get("date"),
        "total": _latest_express.get("total"),
        "groups": _latest_express.get("groups"),
        "high_value_count": _latest_express.get("high_value_count"),
        "priority_count": _latest_express.get("priority_count"),
    }


@router.get("/preview")
async def preview_express_html() -> HTMLResponse:
    """预览标讯速递 HTML（无需认证）。"""
    html = _latest_express.get("html", "<html><body><h2>尚未生成标讯速递</h2></body></html>")
    return HTMLResponse(content=html)


@router.post("/push")
async def push_bidding_express(
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """推送标讯速递到钉钉。"""
    html = _latest_express.get("html")
    if not html:
        raise HTTPException(400, "请先生成标讯速递")

    express_date = _latest_express.get("date", "")
    total = _latest_express.get("total", 0)

    # 构造推送消息
    groups = _latest_express.get("groups", [])
    group_summary = "、".join(f"{g['label']} {g['count']}" for g in groups[:6])

    title = "📋 标讯速递"
    text = (
        f"## 📋 标讯速递 · {express_date}\n\n"
        f"> 共 **{total}** 条标讯\n\n"
        f"{group_summary}\n\n"
    )

    # 高金额标讯
    high_value_count = _latest_express.get("high_value_count", 0)
    if high_value_count:
        text += f"💰 高金额标讯：**{high_value_count}** 条\n\n"

    # 重点匹配
    priority_count = _latest_express.get("priority_count", 0)
    if priority_count:
        text += f"🎯 重点匹配：**{priority_count}** 条\n\n"

    # 预览链接
    base_url = (payload or {}).get("base_url", "")
    preview_url = f"{base_url}/bidding-express/preview" if base_url else "/bidding-express/preview"
    text += f"👉 [点击查看完整标讯速递]({preview_url})\n\n"
    text += "---\n*剑鱼标讯 · 营销数据驾驶舱*"

    # 发送
    result = await dingtalk_service.send_markdown(db, title, text, is_at_all=True)

    return {
        "success": result["success"],
        "message": result["message"],
        "total": total,
        "express_date": express_date,
    }
