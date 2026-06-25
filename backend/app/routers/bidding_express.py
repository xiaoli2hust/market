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

from ..auth import require_permission
from ..config import settings
from ..database import get_db
from ..models import DingtalkConfig
from ..secret_store import decrypt_secret, encrypt_secret
from ..crawlers.bidding_crawler import JianyuBiddingCrawler
from ..services import dingtalk_service
from ..services.bidding_express_service import build_express, render_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bidding-express", tags=["bidding-express"])

# 缓存最新生成的速递
_latest_express: dict[str, Any] = {}


async def _get_api_key(db: AsyncSession) -> str:
    """获取结构化标讯 API key。"""

    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if row and row.jianyu_api_key:
        api_key = decrypt_secret(row.jianyu_api_key)
        if api_key:
            return api_key

    username = (row.jianyu_username if row else None) or settings.JIANYU_USERNAME
    password = (decrypt_secret(row.jianyu_password) if row else None) or settings.JIANYU_PASSWORD
    if username and password:
        try:
            key = await JianyuBiddingCrawler()._discover_api_key(username, password)
        except Exception as exc:  # noqa: BLE001
            logger.warning("structured bidding source login failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="结构化标讯数据源登录或规则发现失败，请检查账号、密码或 API Key 配置",
            ) from exc
        if row:
            row.jianyu_api_key = encrypt_secret(key)
        else:
            db.add(DingtalkConfig(
                jianyu_username=username,
                jianyu_password=encrypt_secret(password),
                jianyu_api_key=encrypt_secret(key),
            ))
        await db.flush()
        return key

    raise HTTPException(400, "结构化标讯 API Key 未配置，请在管理中心 → 接口与密钥 → 结构化标讯数据源配置中填写")


@router.post("/generate")
async def generate_bidding_express(
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:express")),
) -> dict[str, Any]:
    """生成标讯速递。"""
    api_key = await _get_api_key(db)
    payload = payload or {}
    express_date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    period = payload.get("period") or "week"

    try:
        express = build_express(api_key, express_date, period=period)
    except Exception as exc:  # noqa: BLE001
        logger.warning("structured bidding source fetch failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="结构化标讯数据源拉取失败，请检查数据源配置、网络连通性和采集频率",
        ) from exc
    html = render_html(express)
    groups = _express_groups(express)
    priority_count = len(express.priority_items)

    # 缓存
    _latest_express["status"] = "ok" if express.total else "empty"
    _latest_express["html"] = html
    _latest_express["date"] = express_date
    _latest_express["period"] = express.period
    _latest_express["period_label"] = express.period_label
    _latest_express["source_total"] = express.source_total
    _latest_express["total"] = express.total
    _latest_express["groups"] = groups
    _latest_express["high_value_count"] = len(express.high_value_items)
    _latest_express["priority_count"] = priority_count

    return {
        "status": "ok" if express.total else "empty",
        "express_date": express_date,
        "period": express.period,
        "period_label": express.period_label,
        "source_total": express.source_total,
        "total": express.total,
        "groups": groups,
        "high_value_count": len(express.high_value_items),
        "priority_count": priority_count,
        "message": (
            f"生成成功：{express.period_label} 命中 {express.total} 条标讯，来源返回 {express.source_total} 条"
            if express.total
            else f"{express.period_label} 暂无命中标讯，来源返回 {express.source_total} 条"
        ),
    }


@router.get("/latest")
async def get_latest_express(
    _user: dict = Depends(require_permission("dashboard:view")),
) -> dict[str, Any]:
    """获取最新标讯速递概要。"""
    if not _latest_express:
        return {"status": "empty", "message": "尚未生成标讯速递"}
    return {
        "status": _latest_express.get("status", "ok"),
        "express_date": _latest_express.get("date"),
        "period": _latest_express.get("period"),
        "period_label": _latest_express.get("period_label"),
        "source_total": _latest_express.get("source_total"),
        "total": _latest_express.get("total"),
        "groups": _latest_express.get("groups"),
        "high_value_count": _latest_express.get("high_value_count"),
        "priority_count": _latest_express.get("priority_count"),
    }


@router.get("/preview")
async def preview_express_html(
    _user: dict = Depends(require_permission("dashboard:view")),
) -> HTMLResponse:
    """预览标讯速递 HTML。"""
    html = _latest_express.get("html", "<html><body><h2>尚未生成标讯速递</h2></body></html>")
    return HTMLResponse(content=html)


@router.post("/push")
async def push_bidding_express(
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:express")),
) -> dict[str, Any]:
    """推送标讯速递到钉钉。"""
    html = _latest_express.get("html")
    if not html:
        raise HTTPException(400, "请先生成标讯速递")

    express_date = _latest_express.get("date", "")
    period_label = _latest_express.get("period_label") or express_date
    total = _latest_express.get("total", 0)

    # 构造推送消息
    groups = _latest_express.get("groups", [])
    group_summary = "、".join(f"{g['label']} {g['count']}" for g in groups[:6])

    title = "📋 标讯速递"
    text = (
        f"## 📋 标讯速递 · {period_label}\n\n"
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

    # 查看入口：完整预览需要登录系统，避免再次暴露匿名业务页面。
    base_url = (payload or {}).get("base_url", "")
    if base_url:
        text += f"👉 [登录系统查看完整标讯速递]({base_url}/dashboard)\n\n"
    else:
        text += "👉 请登录 Market 数据采集中心查看完整标讯速递\n\n"
    text += "---\n*标讯雷达 · Market 数据采集中心*"

    # 发送
    result = await dingtalk_service.send_markdown(db, title, text, is_at_all=True)

    return {
        "success": result["success"],
        "message": result["message"],
        "total": total,
        "express_date": express_date,
        "period_label": period_label,
    }


def _express_groups(express) -> list[dict[str, Any]]:
    return [
        {
            "subtype": industry.name,
            "label": industry.name,
            "count": industry.total,
        }
        for industry in express.industries
        if industry.total > 0
    ]
