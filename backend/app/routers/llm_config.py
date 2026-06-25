"""大模型配置管理路由。

提供模型配置、Prompt 模板管理、调用统计等接口。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_permission
from ..config import settings
from ..database import get_db
from ..models import LLMCallLog, LLMConfig, PromptTemplate
from ..secret_store import decrypt_secret, encrypt_secret
from ..services.llm_service import create_runtime_llm_service, get_runtime_llm_config
from ..validation import validate_http_url

logger = logging.getLogger(__name__)
LOCAL_TZ = timezone(timedelta(hours=8))

router = APIRouter(prefix="/llm", tags=["llm"])

# 默认 Prompt 模板
DEFAULT_PROMPTS = {
    "daily_parse": {
        "name": "日报解析",
        "template": (
            "你是一个营销活动分析助手。请分析以下工作日报内容，"
            "拆分出每一条具体的工作活动。\n\n"
            "每条活动需要提取：activity_type、target、opportunity、description、confidence\n"
            "activity_type 必须从以下选项中选择：{action_types}\n"
            "严格输出 JSON，不要额外说明。"
        ),
        "temperature": 0.1,
        "max_tokens": 2000,
    },
    "action_classify": {
        "name": "行为分类",
        "template": "请判断以下工作描述属于哪种行为类型：{action_types}\n描述：{text}\n只输出类型名称。",
        "temperature": 0.0,
        "max_tokens": 50,
    },
    "express_summary": {
        "name": "速递摘要",
        "template": "请用一句话概括以下资讯内容（不超过30字）：\n{text}",
        "temperature": 0.3,
        "max_tokens": 100,
    },
    "weekly_summary": {
        "name": "周报总结",
        "template": (
            "请基于以下一周的营销活动记录，生成一份简明的周报总结。\n"
            "包含：重点成果、存在问题、下周建议。\n\n"
            "活动记录：\n{activities}"
        ),
        "temperature": 0.4,
        "max_tokens": 1500,
    },
    "relevance_score": {
        "name": "爬虫相关度评分",
        "template": (
            "请判断以下资讯与营销业务的相关度（0-100分）。\n"
            "关键词参考：{keywords}\n\n"
            "标题：{title}\n摘要：{summary}\n"
            "只输出数字分数。"
        ),
        "temperature": 0.0,
        "max_tokens": 20,
    },
}


# ---------------------------------------------------------------------------
# 模型配置
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> dict[str, Any]:
    """获取 LLM 配置（API Key 脱敏）。"""
    row = (await db.execute(select(LLMConfig).limit(1))).scalar_one_or_none()
    if not row:
        return {
            "model_name": settings.LLM_MODEL,
            "api_base_url": settings.LLM_BASE_URL,
            "api_key_masked": _mask_key(settings.LLM_API_KEY),
            "default_temperature": 0.2,
            "configured": bool(settings.LLM_API_KEY),
        }
    api_key = decrypt_secret(row.api_key)
    return {
        "model_name": row.model_name,
        "api_base_url": row.api_base_url,
        "api_key_masked": _mask_key(api_key),
        "default_temperature": row.default_temperature,
        "configured": bool(api_key),
    }


@router.put("/config")
async def update_llm_config(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> dict[str, Any]:
    """更新 LLM 配置。"""
    if "api_base_url" in payload:
        payload["api_base_url"] = validate_http_url(payload.get("api_base_url"), "API Base URL")
    if "default_temperature" in payload:
        temperature = float(payload["default_temperature"])
        if temperature < 0 or temperature > 2:
            raise HTTPException(status_code=400, detail="模型温度必须在 0-2 之间")
        payload["default_temperature"] = temperature
    row = (await db.execute(select(LLMConfig).limit(1))).scalar_one_or_none()
    if row:
        for field in ("model_name", "api_base_url", "default_temperature"):
            if field in payload:
                setattr(row, field, payload[field])
        if "api_key" in payload and payload["api_key"]:
            row.api_key = encrypt_secret(payload["api_key"])
    else:
        db.add(LLMConfig(
            model_name=payload.get("model_name", settings.LLM_MODEL),
            api_base_url=payload.get("api_base_url", settings.LLM_BASE_URL),
            api_key=encrypt_secret(payload.get("api_key")) if payload.get("api_key") else None,
            default_temperature=payload.get("default_temperature", 0.2),
        ))
    return {"status": "ok"}


@router.post("/test")
async def test_llm_connection(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> dict[str, Any]:
    """测试 LLM 连通性。"""
    effective = await get_runtime_llm_config(db)
    api_key = effective["api_key"]

    if not api_key:
        return {"success": False, "message": "API Key 未配置"}

    try:
        llm = await create_runtime_llm_service(db, timeout=15, scene="connection_test")
        resp = await llm.chat(
            [{"role": "user", "content": "回复OK即可"}],
            temperature=0,
            scene="connection_test",
        )
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"success": True, "message": f"连接成功，模型响应：{content[:50]}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败：{str(e)[:200]}"}


# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------


@router.get("/prompts")
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> list[dict[str, Any]]:
    """获取所有 Prompt 模板。"""
    rows = (await db.execute(
        select(PromptTemplate).order_by(PromptTemplate.scene)
    )).scalars().all()

    if not rows:
        # 返回默认模板
        return [
            {"scene": scene, **data} for scene, data in DEFAULT_PROMPTS.items()
        ]
    return [
        {
            "scene": r.scene,
            "name": r.name,
            "template": r.template_text,
            "temperature": r.temperature,
            "max_tokens": r.max_tokens,
        }
        for r in rows
    ]


@router.put("/prompts/{scene}")
async def update_prompt(
    scene: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> dict[str, Any]:
    """更新某个场景的 Prompt 模板。"""
    existing = (await db.execute(
        select(PromptTemplate).where(PromptTemplate.scene == scene)
    )).scalar_one_or_none()

    defaults = DEFAULT_PROMPTS.get(scene, {})
    if existing:
        existing.name = payload.get("name", existing.name)
        existing.template_text = payload.get("template", existing.template_text)
        existing.temperature = payload.get("temperature", existing.temperature)
        existing.max_tokens = payload.get("max_tokens", existing.max_tokens)
    else:
        db.add(PromptTemplate(
            scene=scene,
            name=payload.get("name", defaults.get("name", scene)),
            template_text=payload.get("template", defaults.get("template", "")),
            temperature=payload.get("temperature", defaults.get("temperature", 0.2)),
            max_tokens=payload.get("max_tokens", defaults.get("max_tokens", 2000)),
        ))
    return {"scene": scene, "status": "ok"}


# ---------------------------------------------------------------------------
# 调用统计
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_llm_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permission("management:llm")),
) -> dict[str, Any]:
    """基于调用审计表返回真实 LLM 调用统计。"""

    today_start, week_start = _stats_windows()
    today_calls, today_tokens, today_latency, today_errors = await _window_stats(db, today_start)
    week_calls, week_tokens, week_latency, week_errors = await _window_stats(db, week_start)

    scene_rows = (
        await db.execute(
            select(
                LLMCallLog.scene,
                func.count(LLMCallLog.id),
                func.coalesce(func.sum(LLMCallLog.total_tokens), 0),
                func.coalesce(func.sum(case((LLMCallLog.status == "error", 1), else_=0)), 0),
            )
            .where(LLMCallLog.created_at >= week_start)
            .group_by(LLMCallLog.scene)
            .order_by(func.count(LLMCallLog.id).desc())
        )
    ).all()
    recent_errors = (
        await db.execute(
            select(LLMCallLog)
            .where(LLMCallLog.status == "error")
            .order_by(LLMCallLog.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    return {
        "implemented": True,
        "message": "统计来自真实调用审计记录。",
        "today_calls": today_calls,
        "todayTokens": today_tokens,
        "todayAvgLatencyMs": today_latency,
        "todayErrors": today_errors,
        "weekCalls": week_calls,
        "weekTokens": week_tokens,
        "weekAvgLatencyMs": week_latency,
        "weekErrors": week_errors,
        "byScene": {
            scene: {"calls": calls, "tokens": tokens, "errors": errors}
            for scene, calls, tokens, errors in scene_rows
        },
        "recentErrors": [
            {
                "scene": row.scene,
                "model_name": row.model_name,
                "error_message": row.error_message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent_errors
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_key(key: str | None) -> str:
    if not key:
        return "(not configured)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


def _stats_windows() -> tuple[datetime, datetime]:
    now = datetime.now(LOCAL_TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    return today_start.astimezone(timezone.utc), week_start.astimezone(timezone.utc)


async def _window_stats(db: AsyncSession, start_at: datetime) -> tuple[int, int, int, int]:
    row = (
        await db.execute(
            select(
                func.count(LLMCallLog.id),
                func.coalesce(func.sum(LLMCallLog.total_tokens), 0),
                func.coalesce(func.avg(LLMCallLog.latency_ms), 0),
                func.coalesce(func.sum(case((LLMCallLog.status == "error", 1), else_=0)), 0),
            ).where(LLMCallLog.created_at >= start_at)
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0), int(row[3] or 0)
