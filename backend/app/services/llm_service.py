"""LLM 服务：通义千问 OpenAI 兼容接口封装。

职责：
- 行为抽取：将日报原文解析为结构化活动数据；
- 通用 chat 接口：供后续模块（活动归一化、报告生成等）复用。

设计要点：
- 网络/解析失败均返回空列表 + 写日志，绝不抛到上层路由；
- ``response_format=json_object`` 部分 Qwen 模型不兼容，做正则兜底；
- LLM_API_KEY 未配置时直接返回空列表，让上游仅落地原始文件。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import LLMCallLog, LLMConfig, PromptTemplate
from ..secret_store import decrypt_secret

logger = logging.getLogger(__name__)


# 行为标签：与产品评审对齐的固定枚举，必须传给 LLM 让其从中选择。
ACTION_TYPES: list[str] = [
    "拜访客户",
    "商机跟进",
    "方案撰写",
    "项目推进",
    "渠道拓展",
    "回款跟进",
    "内部协作",
    "技术交流",
    "POC测试",
    "招投标",
    "合同谈判",
    "客户维护",
    "其他",
]


_JSON_ARRAY_RE = re.compile(r"\[\s*[\s\S]*?\s*\]", re.MULTILINE)
_JSON_OBJECT_RE = re.compile(r"\{\s*[\s\S]*?\s*\}", re.MULTILINE)


class LLMService:
    """通义千问对话 API 客户端封装。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        audit_db: AsyncSession | None = None,
        default_scene: str = "generic",
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self._timeout = timeout
        self._audit_db = audit_db
        self._default_scene = default_scene

    # ---------- 内部工具 ----------

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        scene: str | None = None,
    ) -> dict[str, Any]:
        """通用 chat.completions 调用。返回原始 JSON。"""

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if extra:
            payload.update(extra)

        scene_name = scene or self._default_scene
        started = time.perf_counter()
        try:
            url = f"{self.base_url}/chat/completions"
            headers = self._headers()
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            self._record_call_log(
                scene=scene_name,
                status="success",
                response=data,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            return data
        except Exception as exc:
            self._record_call_log(
                scene=scene_name,
                status="error",
                response=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_message=_short_error_message(exc),
            )
            raise

    def _record_call_log(
        self,
        *,
        scene: str,
        status: str,
        response: dict[str, Any] | None,
        latency_ms: int,
        error_message: str | None = None,
    ) -> None:
        """把一次模型调用写入当前事务；审计失败不影响主流程。"""

        if self._audit_db is None:
            return
        try:
            usage = response.get("usage") if isinstance(response, dict) else {}
            prompt_tokens = _int_usage(usage, "prompt_tokens")
            completion_tokens = _int_usage(usage, "completion_tokens")
            total_tokens = _int_usage(usage, "total_tokens") or (prompt_tokens + completion_tokens)
            self._audit_db.add(
                LLMCallLog(
                    scene=(scene or "generic")[:50],
                    model_name=self.model,
                    api_base_url=self.base_url,
                    status=status,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    error_message=(error_message or "")[:1000] or None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        except Exception as audit_error:  # noqa: BLE001
            logger.warning("LLM 调用审计写入失败：%s", audit_error)

    async def extract_activities(self, chat_text: str) -> list[dict[str, Any]]:
        """兼容旧调用名：将聊天文本作为日报原文抽取活动。"""

        return await parse_daily_report(user_name="", report_text=chat_text, service=self)


async def get_runtime_llm_config(db: AsyncSession | None = None) -> dict[str, Any]:
    """Load effective LLM config, preferring management-center settings."""

    if db is not None:
        row = (await db.execute(select(LLMConfig).limit(1))).scalar_one_or_none()
        if row:
            return {
                "api_key": decrypt_secret(row.api_key) or settings.LLM_API_KEY,
                "base_url": row.api_base_url or settings.LLM_BASE_URL,
                "model": row.model_name or settings.LLM_MODEL,
                "temperature": row.default_temperature,
                "source": "management",
            }
    return {
        "api_key": settings.LLM_API_KEY,
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
        "temperature": 0.2,
        "source": "environment",
    }


async def create_runtime_llm_service(
    db: AsyncSession | None = None,
    *,
    timeout: float = 60.0,
    scene: str = "generic",
) -> LLMService:
    """Create an LLM client from the effective runtime configuration."""

    config = await get_runtime_llm_config(db)
    return LLMService(
        api_key=config["api_key"],
        base_url=config["base_url"],
        model=config["model"],
        timeout=timeout,
        audit_db=db,
        default_scene=scene,
    )


async def get_prompt_template(
    db: AsyncSession | None,
    scene: str,
    default_template: str,
    *,
    default_temperature: float = 0.2,
    default_max_tokens: int = 2000,
) -> dict[str, Any]:
    """Load a prompt template from DB, falling back to code defaults."""

    if db is not None:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.scene == scene))
        ).scalar_one_or_none()
        if row:
            return {
                "template": row.template_text,
                "temperature": row.temperature,
                "max_tokens": row.max_tokens,
                "source": "management",
            }
    return {
        "template": default_template,
        "temperature": default_temperature,
        "max_tokens": default_max_tokens,
        "source": "default",
    }


def _build_prompt(user_name: str, report_text: str, template: str | None = None) -> str:
    """构造行为抽取 prompt。"""

    user_hint = f"汇报人：{user_name}\n" if user_name else ""
    if template:
        return (
            template
            .replace("{action_types}", "、".join(ACTION_TYPES))
            .replace("{user_name}", user_name or "")
            .replace("{report_text}", report_text)
            .replace("{text}", report_text)
        )
    return (
        "你是一个营销活动分析助手。请分析以下工作日报内容，"
        "拆分出每一条具体的工作活动。\n\n"
        "每条活动需要提取以下字段：\n"
        f"- activity_type: 必须从以下选项中选择最匹配的一个：{ACTION_TYPES}\n"
        "- target: 客户或工作对象名称（公司/单位/部门），无法识别时填空字符串\n"
        "- opportunity: 相关的商机或项目名称，没有时填空字符串\n"
        "- description: 一句话描述具体做了什么，避免照抄日报标题\n"
        "- confidence: 你对这条提取结果的置信度，范围 0-1 的浮点数\n\n"
        "要求：\n"
        "1. 严格输出 JSON，不要任何额外说明文字、不要 Markdown 代码块；\n"
        "2. 顶层为对象，键名为 activities，值为数组；\n"
        "3. 一条活动只对应一件事，避免合并多个客户/项目；\n"
        "4. 如果日报中没有可提取的活动，activities 返回空数组。\n\n"
        f"{user_hint}日报原文：\n{report_text}\n\n"
        "示例输出：\n"
        '{"activities": [{"activity_type": "方案撰写", "target": "广州交研院", '
        '"opportunity": "广州交研院物流数据集项目", "description": '
        '"完成内部需求反馈澄清", "confidence": 0.9}]}'
    )


def _extract_json_payload(text: str) -> Any | None:
    """从 LLM 输出中提取 JSON。

    优先按整体解析，失败时退化为正则提取首段 ``{...}`` 或 ``[...]``。
    """

    if not text:
        return None
    text = text.strip()
    # 去除可能的 ```json ... ``` 包裹
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 兜底 1：寻找首个 JSON 对象
    obj_match = _JSON_OBJECT_RE.search(text)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    # 兜底 2：寻找首个 JSON 数组
    arr_match = _JSON_ARRAY_RE.search(text)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            return None

    return None


def _int_usage(usage: Any, key: str) -> int:
    if not isinstance(usage, dict):
        return 0
    try:
        return int(usage.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _short_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text[:500] if exc.response is not None else ""
        return f"HTTP {exc.response.status_code}: {body}"
    return str(exc)[:500]


def _normalize_activities(raw: Any) -> list[dict[str, Any]]:
    """统一不同 LLM 输出形态为活动列表。"""

    if raw is None:
        return []

    if isinstance(raw, dict):
        # 常见包装：{"activities": [...]} / {"data": [...]} / {"result": [...]}
        for key in ("activities", "data", "result", "items", "list"):
            value = raw.get(key)
            if isinstance(value, list):
                raw = value
                break
        else:
            # 单条对象也兼容
            if "activity_type" in raw:
                raw = [raw]
            else:
                return []

    if not isinstance(raw, list):
        return []

    activities: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        activity_type = str(item.get("activity_type") or "").strip() or "其他"
        if activity_type not in ACTION_TYPES:
            activity_type = "其他"
        target = (item.get("target") or "").strip() or None
        opportunity = (item.get("opportunity") or "").strip() or None
        description = (item.get("description") or "").strip() or None
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))

        activities.append(
            {
                "activity_type": activity_type,
                "target": target,
                "opportunity": opportunity,
                "description": description,
                "confidence": confidence,
            }
        )
    return activities


async def parse_daily_report(
    user_name: str,
    report_text: str,
    *,
    service: LLMService | None = None,
    db: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """用通义千问解析日报原文，返回结构化活动列表。

    任何异常（API Key 缺失、网络错误、非 JSON 响应等）均返回空列表，
    并通过日志记录原因，避免影响上游原始文件落库。
    """

    if not report_text or not report_text.strip():
        return []

    llm = service or await create_runtime_llm_service(db, scene="daily_parse")
    if not llm.api_key:
        logger.info("LLM_API_KEY 未配置，跳过日报解析（user=%s）", user_name)
        return []

    prompt_config = await get_prompt_template(
        db,
        "daily_parse",
        _build_prompt(user_name=user_name, report_text=report_text),
        default_temperature=0.1,
        default_max_tokens=2000,
    )
    prompt = _build_prompt(
        user_name=user_name,
        report_text=report_text,
        template=prompt_config["template"],
    )
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的营销活动数据提取助手，只输出 JSON 格式数据。",
        },
        {"role": "user", "content": prompt},
    ]

    # 优先尝试 json_object 模式；若 400/不支持则降级重试。
    response: dict[str, Any] | None = None
    try:
        response = await llm.chat(
            messages,
            temperature=float(prompt_config["temperature"]),
            response_format={"type": "json_object"},
            extra={"max_tokens": int(prompt_config["max_tokens"])},
            scene="daily_parse",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 422):
            logger.warning(
                "LLM 不支持 response_format，降级为普通 chat：%s", exc.response.text
            )
            try:
                response = await llm.chat(
                    messages,
                    temperature=float(prompt_config["temperature"]),
                    extra={"max_tokens": int(prompt_config["max_tokens"])},
                    scene="daily_parse",
                )
            except Exception as inner:  # noqa: BLE001
                logger.exception("LLM 调用失败（降级模式）：%s", inner)
                return []
        else:
            logger.exception(
                "LLM 调用失败：status=%s body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            return []
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.exception("LLM 调用网络异常：%s", exc)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM 调用未知异常：%s", exc)
        return []

    if not response:
        return []

    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("LLM 响应结构异常：%s, raw=%s", exc, response)
        return []

    payload = _extract_json_payload(content)
    if payload is None:
        logger.error("LLM 输出无法解析为 JSON：%s", content[:500])
        return []

    activities = _normalize_activities(payload)
    logger.info("LLM 解析完成（user=%s）：%d 条活动", user_name, len(activities))
    return activities


def get_llm_service() -> LLMService:
    """便捷工厂，便于在路由依赖注入中使用。"""

    return LLMService()


__all__ = [
    "ACTION_TYPES",
    "LLMService",
    "create_runtime_llm_service",
    "get_llm_service",
    "get_prompt_template",
    "get_runtime_llm_config",
    "parse_daily_report",
]
