"""大模型配置管理路由。

提供模型配置、Prompt 模板管理、调用统计等接口。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import LLMConfig, PromptTemplate

logger = logging.getLogger(__name__)

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
    _user: dict = Depends(get_current_user),
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
    return {
        "model_name": row.model_name,
        "api_base_url": row.api_base_url,
        "api_key_masked": _mask_key(row.api_key),
        "default_temperature": row.default_temperature,
        "configured": bool(row.api_key),
    }


@router.put("/config")
async def update_llm_config(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """更新 LLM 配置。"""
    row = (await db.execute(select(LLMConfig).limit(1))).scalar_one_or_none()
    if row:
        for field in ("model_name", "api_base_url", "default_temperature"):
            if field in payload:
                setattr(row, field, payload[field])
        if "api_key" in payload and payload["api_key"]:
            row.api_key = payload["api_key"]
    else:
        db.add(LLMConfig(
            model_name=payload.get("model_name", settings.LLM_MODEL),
            api_base_url=payload.get("api_base_url", settings.LLM_BASE_URL),
            api_key=payload.get("api_key"),
            default_temperature=payload.get("default_temperature", 0.2),
        ))
    return {"status": "ok"}


@router.post("/test")
async def test_llm_connection(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """测试 LLM 连通性。"""
    from ..services.llm_service import LLMService

    row = (await db.execute(select(LLMConfig).limit(1))).scalar_one_or_none()
    api_key = row.api_key if row else settings.LLM_API_KEY
    base_url = row.api_base_url if row else settings.LLM_BASE_URL
    model = row.model_name if row else settings.LLM_MODEL

    if not api_key:
        return {"success": False, "message": "API Key 未配置"}

    try:
        llm = LLMService(api_key=api_key, base_url=base_url, model=model, timeout=15)
        resp = await llm.chat(
            [{"role": "user", "content": "回复OK即可"}],
            temperature=0,
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
    _user: dict = Depends(get_current_user),
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
    _user: dict = Depends(get_current_user),
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
# 调用统计（简化版，返回模拟数据）
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_llm_stats(
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """LLM 调用统计（当前返回模拟数据，后续接入实际统计）。"""
    return {
        "today_calls": 12,
        "todayTokens": 8500,
        "weekCalls": 67,
        "weekTokens": 45200,
        "byScene": {
            "daily_parse": 5,
            "express_summary": 4,
            "relevance_score": 2,
            "weekly_summary": 1,
        },
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
