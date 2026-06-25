"""钉钉推送服务。

核心功能：
- HMAC-SHA256 加签发送（自定义机器人 Webhook）
- 文本 / Markdown / Markdown+图片 消息
- 企业内部应用 Token 获取 & 图片上传（用于长图推送）
"""

from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import DingtalkConfig
from ..secret_store import decrypt_secret

logger = logging.getLogger(__name__)

_DINGTALK_WEBHOOK_HOST = "oapi.dingtalk.com"
_DINGTALK_WEBHOOK_PATH = "/robot/send"
_DINGTALK_MIN_SEND_INTERVAL_SECONDS = 3.1
_SUPPORTED_WEBHOOK_MSGTYPES = {"text", "markdown", "link", "actionCard", "feedCard"}
_last_webhook_send_at: dict[str, float] = {}
_webhook_rate_limit_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Webhook 配置读取
# ---------------------------------------------------------------------------


async def get_webhook_config(db: AsyncSession) -> dict[str, Any]:
    """从数据库读取钉钉配置，fallback 到环境变量。

    返回字典：
    {
        "webhook_url": str | None,
        "secret": str | None,
        "app_key": str | None,
        "app_secret": str | None,
        "delivery_mode": "webhook" | "openapi",
        "robot_code": str | None,
        "open_conversation_id": str | None,
        "cool_app_code": str | None,
    }
    """
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if row:
        return {
            "webhook_url": decrypt_secret(row.webhook_url) or settings.DINGTALK_WEBHOOK_URL or None,
            "secret": decrypt_secret(row.secret) or settings.DINGTALK_SECRET or None,
            "app_key": getattr(row, "app_key", None) or None,
            "app_secret": decrypt_secret(getattr(row, "app_secret", None)) or None,
            "delivery_mode": getattr(row, "delivery_mode", None) or "webhook",
            "robot_code": getattr(row, "robot_code", None) or None,
            "open_conversation_id": getattr(row, "open_conversation_id", None) or None,
            "cool_app_code": getattr(row, "cool_app_code", None) or None,
        }
    return {
        "webhook_url": settings.DINGTALK_WEBHOOK_URL or None,
        "secret": settings.DINGTALK_SECRET or None,
        "app_key": None,
        "app_secret": None,
        "delivery_mode": "webhook",
        "robot_code": None,
        "open_conversation_id": None,
        "cool_app_code": None,
    }


# ---------------------------------------------------------------------------
# HMAC-SHA256 签名
# ---------------------------------------------------------------------------


def validate_custom_robot_webhook_url(webhook_url: str, *, allow_empty: bool = False) -> str:
    """Validate a DingTalk custom robot Webhook URL.

    钉钉自定义机器人 Webhook 应为：
    https://oapi.dingtalk.com/robot/send?access_token=...
    """

    value = (webhook_url or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ValueError("Webhook URL 未配置")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("钉钉机器人 Webhook 必须使用 HTTPS")
    if parsed.netloc.lower() != _DINGTALK_WEBHOOK_HOST or parsed.path != _DINGTALK_WEBHOOK_PATH:
        raise ValueError("Webhook URL 必须是钉钉自定义机器人地址")
    query = urllib.parse.parse_qs(parsed.query)
    access_token = (query.get("access_token") or [""])[0].strip()
    if not access_token:
        raise ValueError("Webhook URL 缺少 access_token")
    return value


def normalize_custom_robot_secret(secret: str | None) -> str:
    """Normalize and validate DingTalk custom robot signing secret."""

    value = (secret or "").strip()
    if value and not value.startswith("SEC"):
        raise ValueError("Secret 应为钉钉机器人加签密钥，通常以 SEC 开头")
    return value


def _sign(secret: str, timestamp: str | None = None) -> tuple[str, str]:
    """生成钉钉加签参数。

    返回 (timestamp, sign) 二元组。
    """
    timestamp = timestamp or str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def _build_webhook_url(webhook_url: str, secret: str | None) -> str:
    """如果配置了 secret，给 webhook URL 追加 timestamp + sign 参数。"""
    webhook_url = _strip_dynamic_signature_params(validate_custom_robot_webhook_url(webhook_url))
    if not secret:
        return webhook_url
    secret = normalize_custom_robot_secret(secret)
    timestamp, sign = _sign(secret)
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


def _strip_dynamic_signature_params(webhook_url: str) -> str:
    parsed = urllib.parse.urlparse(webhook_url)
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"timestamp", "sign"}
    ]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_pairs)))


def _webhook_rate_key(webhook_url: str) -> str:
    parsed = urllib.parse.urlparse(webhook_url)
    access_token = (urllib.parse.parse_qs(parsed.query).get("access_token") or [""])[0]
    return access_token or f"{parsed.netloc}{parsed.path}"


async def _respect_dingtalk_rate_limit(webhook_url: str) -> None:
    """Best-effort guard for DingTalk's custom robot 20 messages/minute limit."""

    key = _webhook_rate_key(webhook_url)
    async with _webhook_rate_limit_lock:
        now = time.monotonic()
        last_at = _last_webhook_send_at.get(key)
        if last_at is not None:
            wait_seconds = _DINGTALK_MIN_SEND_INTERVAL_SECONDS - (now - last_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
        _last_webhook_send_at[key] = time.monotonic()


def _validate_webhook_message(msg_body: dict[str, Any]) -> None:
    msgtype = str(msg_body.get("msgtype") or "").strip()
    if msgtype not in _SUPPORTED_WEBHOOK_MSGTYPES:
        raise ValueError("钉钉消息类型不支持")
    if msgtype == "text":
        content = ((msg_body.get("text") or {}).get("content") or "").strip()
        if not content:
            raise ValueError("文本消息内容不能为空")
    elif msgtype == "markdown":
        markdown = msg_body.get("markdown") or {}
        if not str(markdown.get("title") or "").strip():
            raise ValueError("Markdown 消息标题不能为空")
        if not str(markdown.get("text") or "").strip():
            raise ValueError("Markdown 消息正文不能为空")
    elif msgtype == "link":
        link = msg_body.get("link") or {}
        for field in ("title", "text", "messageUrl"):
            if not str(link.get(field) or "").strip():
                raise ValueError("Link 消息缺少必要字段")
    elif msgtype == "actionCard":
        card = msg_body.get("actionCard") or {}
        if not str(card.get("title") or "").strip() or not str(card.get("text") or "").strip():
            raise ValueError("ActionCard 消息标题和正文不能为空")
    elif msgtype == "feedCard":
        links = (msg_body.get("feedCard") or {}).get("links") or []
        if not isinstance(links, list) or not links:
            raise ValueError("FeedCard 消息至少需要一个链接")

    at = msg_body.get("at")
    if at is not None and not isinstance(at, dict):
        raise ValueError("at 字段格式不正确")


# ---------------------------------------------------------------------------
# Webhook 消息发送
# ---------------------------------------------------------------------------


async def send_webhook_message(
    webhook_url: str,
    secret: str | None,
    msg_body: dict[str, Any],
) -> dict[str, Any]:
    """发送消息到钉钉自定义机器人 Webhook（自动加签）。

    返回 {"success": bool, "message": str, "raw": dict}
    """
    try:
        _validate_webhook_message(msg_body)
        clean_webhook_url = validate_custom_robot_webhook_url(webhook_url)
        clean_secret = normalize_custom_robot_secret(secret)
        await _respect_dingtalk_rate_limit(clean_webhook_url)
        url = _build_webhook_url(clean_webhook_url, clean_secret)
    except ValueError as exc:
        return {"success": False, "message": str(exc), "raw": {}}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=msg_body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            if resp.status_code == 200:
                try:
                    body = resp.json()
                except ValueError:
                    return {"success": False, "message": "钉钉返回内容不是 JSON", "raw": {}}
                if body.get("errcode") == 0:
                    return {"success": True, "message": "推送成功", "raw": body}
                return {
                    "success": False,
                    "message": f"钉钉返回错误: {body.get('errmsg', '未知错误')}",
                    "raw": body,
                }
            return {"success": False, "message": f"钉钉接口 HTTP {resp.status_code}", "raw": {}}
    except httpx.TimeoutException:
        return {"success": False, "message": "请求超时", "raw": {}}
    except Exception as e:
        logger.exception("钉钉推送失败")
        return {"success": False, "message": f"请求失败: {str(e)[:200]}", "raw": {}}


def _openapi_ready(cfg: dict[str, Any]) -> bool:
    return bool(
        cfg.get("app_key")
        and cfg.get("app_secret")
        and cfg.get("robot_code")
        and cfg.get("open_conversation_id")
    )


async def send_openapi_group_message(
    *,
    app_key: str,
    app_secret: str,
    robot_code: str,
    open_conversation_id: str,
    msg_key: str,
    msg_param: dict[str, Any],
    cool_app_code: str | None = None,
) -> dict[str, Any]:
    """Send a DingTalk app robot group message through OpenAPI."""

    token = await get_access_token(app_key, app_secret)
    if not token:
        return {"success": False, "message": "获取钉钉 accessToken 失败", "raw": {}}

    payload: dict[str, Any] = {
        "robotCode": robot_code.strip(),
        "openConversationId": open_conversation_id.strip(),
        "msgKey": msg_key,
        "msgParam": json.dumps(msg_param, ensure_ascii=False),
    }
    if cool_app_code:
        payload["coolAppCode"] = cool_app_code.strip()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_DINGTALK_API_BASE}/v1.0/robot/groupMessages/send",
                json=payload,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "x-acs-dingtalk-access-token": token,
                },
            )
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if 200 <= resp.status_code < 300:
            errcode = body.get("errcode")
            code = body.get("code")
            if errcode not in (None, 0) or code not in (None, "0", 0):
                return {"success": False, "message": body.get("message") or body.get("errmsg") or "钉钉返回错误", "raw": body}
            return {"success": True, "message": "推送成功", "raw": body}
        return {
            "success": False,
            "message": body.get("message") or body.get("errmsg") or f"钉钉接口 HTTP {resp.status_code}",
            "raw": body,
        }
    except httpx.TimeoutException:
        return {"success": False, "message": "请求超时", "raw": {}}
    except Exception as e:
        logger.exception("钉钉 OpenAPI 推送失败")
        return {"success": False, "message": f"请求失败: {str(e)[:200]}", "raw": {}}


async def send_text(
    db: AsyncSession,
    content: str,
    at_mobiles: list[str] | None = None,
) -> dict[str, Any]:
    """发送文本消息。"""
    cfg = await get_webhook_config(db)
    if cfg.get("delivery_mode") == "openapi":
        if not _openapi_ready(cfg):
            return {"success": False, "message": "OpenAPI 机器人配置不完整"}
        return await send_openapi_group_message(
            app_key=cfg["app_key"],
            app_secret=cfg["app_secret"],
            robot_code=cfg["robot_code"],
            open_conversation_id=cfg["open_conversation_id"],
            msg_key="sampleText",
            msg_param={"content": content},
            cool_app_code=cfg.get("cool_app_code"),
        )

    if not cfg["webhook_url"]:
        return {"success": False, "message": "Webhook URL 未配置"}

    msg: dict[str, Any] = {
        "msgtype": "text",
        "text": {"content": content},
    }
    if at_mobiles:
        msg["at"] = {"atMobiles": at_mobiles, "isAtAll": False}

    return await send_webhook_message(cfg["webhook_url"], cfg["secret"], msg)


async def send_markdown(
    db: AsyncSession,
    title: str,
    text: str,
    at_mobiles: list[str] | None = None,
    is_at_all: bool = False,
) -> dict[str, Any]:
    """发送 Markdown 消息。

    Args:
        title: 消息标题（通知栏显示）
        text: Markdown 正文（支持标题、加粗、链接、图片、有序/无序列表）
        at_mobiles: @指定人的手机号列表
        is_at_all: 是否@所有人
    """
    cfg = await get_webhook_config(db)
    if cfg.get("delivery_mode") == "openapi":
        if not _openapi_ready(cfg):
            return {"success": False, "message": "OpenAPI 机器人配置不完整"}
        return await send_openapi_group_message(
            app_key=cfg["app_key"],
            app_secret=cfg["app_secret"],
            robot_code=cfg["robot_code"],
            open_conversation_id=cfg["open_conversation_id"],
            msg_key="sampleMarkdown",
            msg_param={"title": title, "text": text},
            cool_app_code=cfg.get("cool_app_code"),
        )

    if not cfg["webhook_url"]:
        return {"success": False, "message": "Webhook URL 未配置"}

    msg: dict[str, Any] = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }
    if at_mobiles or is_at_all:
        msg["at"] = {
            "atMobiles": at_mobiles or [],
            "isAtAll": is_at_all,
        }

    return await send_webhook_message(cfg["webhook_url"], cfg["secret"], msg)


async def send_markdown_with_image(
    db: AsyncSession,
    title: str,
    text: str,
    image_url: str,
    is_at_all: bool = False,
) -> dict[str, Any]:
    """发送 Markdown 消息（内嵌图片）。

    钉钉 Markdown 支持 ![](image_url) 语法嵌入图片。
    image_url 必须是钉钉服务器可访问的公网 URL。
    """
    # 在 Markdown 正文顶部插入图片
    full_text = f"![screenshot]({image_url})\n\n{text}"
    return await send_markdown(db, title, full_text, is_at_all=is_at_all)


# ---------------------------------------------------------------------------
# 企业内部应用 — 图片上传（用于长图推送）
# ---------------------------------------------------------------------------


_DINGTALK_OAPI_BASE = "https://oapi.dingtalk.com"
_DINGTALK_API_BASE = "https://api.dingtalk.com"


async def get_access_token(app_key: str, app_secret: str) -> Optional[str]:
    """获取企业内部应用 access_token。"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_DINGTALK_API_BASE}/v1.0/oauth2/accessToken",
                json={"appKey": app_key, "appSecret": app_secret},
            )
            if resp.status_code == 200:
                body = resp.json()
                return body.get("accessToken")
            logger.error("获取钉钉 token 失败: HTTP %s %s", resp.status_code, resp.text[:200])
            return None
    except Exception:
        logger.exception("获取钉钉 token 异常")
        return None


async def upload_media(
    access_token: str,
    image_path: str,
    media_type: str = "image",
) -> Optional[str]:
    """上传图片到钉钉，返回 media_id。

    使用旧版 oapi 接口（自定义机器人不支持的备选方案）。
    """
    import os

    if not os.path.isfile(image_path):
        logger.error("截图文件不存在: %s", image_path)
        return None

    file_name = os.path.basename(image_path)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(image_path, "rb") as f:
                resp = await client.post(
                    f"{_DINGTALK_OAPI_BASE}/media/upload",
                    params={"access_token": access_token, "type": media_type},
                    files={"media": (file_name, f, "image/png")},
                )
            if resp.status_code == 200:
                body = resp.json()
                if body.get("errcode") == 0:
                    return body.get("media_id")
                logger.error("钉钉图片上传失败: %s", body.get("errmsg", ""))
                return None
            logger.error("钉钉图片上传 HTTP %s", resp.status_code)
            return None
    except Exception:
        logger.exception("钉钉图片上传异常")
        return None


async def push_express_with_image(
    db: AsyncSession,
    title: str,
    text: str,
    image_path: str,
) -> dict[str, Any]:
    """推送速递长图到钉钉。

    流程：
    1. 获取企业内部应用 access_token
    2. 上传截图获取 media_id
    3. 发送 Markdown 消息（含图片描述 + 链接）

    如果企业应用未配置或上传失败，降级为纯 Markdown 链接消息。
    """
    cfg = await get_webhook_config(db)

    # 尝试上传图片
    image_url = None
    if cfg["app_key"] and cfg["app_secret"]:
        token = await get_access_token(cfg["app_key"], cfg["app_secret"])
        if token:
            media_id = await upload_media(token, image_path)
            if media_id:
                # 钉钉 Markdown 不直接展示 media_id，统一回落到可审计的报告链接。
                logger.info("图片上传成功 media_id=%s（钉钉 Webhook 不支持 media_id 直接展示）", media_id)

    # 降级方案：发送 Markdown + 链接
    # 钉钉自定义机器人 Markdown 支持 ![](url) 但需要公网可访问的 URL
    # 最可靠的方式是发送 Markdown 摘要 + 查看链接
    return await send_markdown(db, title, text, is_at_all=True)


# ---------------------------------------------------------------------------
# 便捷方法：构造推送内容
# ---------------------------------------------------------------------------


def build_report_markdown(
    report_title: str,
    report_type: str,
    report_date: str,
    share_url: str,
    note: str | None = None,
    base_url: str = "",
) -> tuple[str, str]:
    """构造报告推送的 Markdown 消息。

    返回 (title, text) 二元组，可直接传给 send_markdown。
    """
    type_label = "日报" if report_type == "daily" else "周报"
    full_url = f"{base_url}{share_url}" if base_url else share_url

    lines = [
        f"## 📊 {report_title}",
        "",
        f"> **类型**：{type_label}  ",
        f"> **日期**：{report_date}  ",
    ]
    if note:
        lines.append(f"> **备注**：{note}  ")
    lines.extend([
        "",
        f"👉 [点击查看完整报告]({full_url})",
        "",
        "---",
        "*Market 数据采集中心 · 自动推送*",
    ])

    title = f"Market 数据采集中心 · {type_label}"
    text = "\n".join(lines)
    return title, text


def build_express_markdown(
    express_title: str,
    sections: list[dict],
    share_url: str,
    base_url: str = "",
) -> tuple[str, str]:
    """构造速递推送的 Markdown 消息。

    返回 (title, text) 二元组。
    """
    full_url = f"{base_url}{share_url}" if base_url else share_url

    # 统计摘要
    total = sum(s.get("count", 0) for s in sections)
    section_lines = []
    for s in sections:
        emoji = {"bidding": "📋", "news": "📰", "competitor": "🔍", "ai": "🤖"}.get(
            s.get("category", ""), "📌"
        )
        section_lines.append(f"- {emoji} {s.get('type', s.get('category', ''))}：{s.get('count', 0)} 条")

    lines = [
        f"## 📨 {express_title}",
        "",
        f"> 今日共采集 **{total}** 条情报",
        "",
        *section_lines,
        "",
        f"👉 [点击查看完整速递]({full_url})",
        "",
        "---",
        "*Market 数据采集中心 · 每日速递*",
    ]

    title = "Market 数据采集中心 · 每日速递"
    text = "\n".join(lines)
    return title, text
