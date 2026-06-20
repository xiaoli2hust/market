"""钉钉推送服务。

核心功能：
- HMAC-SHA256 加签发送（自定义机器人 Webhook）
- 文本 / Markdown / Markdown+图片 消息
- 企业内部应用 Token 获取 & 图片上传（用于长图推送）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import DingtalkConfig

logger = logging.getLogger(__name__)


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
    }
    """
    row = (await db.execute(select(DingtalkConfig).limit(1))).scalar_one_or_none()
    if row:
        return {
            "webhook_url": row.webhook_url or settings.DINGTALK_WEBHOOK_URL or None,
            "secret": row.secret or settings.DINGTALK_SECRET or None,
            "app_key": getattr(row, "app_key", None) or None,
            "app_secret": getattr(row, "app_secret", None) or None,
        }
    return {
        "webhook_url": settings.DINGTALK_WEBHOOK_URL or None,
        "secret": settings.DINGTALK_SECRET or None,
        "app_key": None,
        "app_secret": None,
    }


# ---------------------------------------------------------------------------
# HMAC-SHA256 签名
# ---------------------------------------------------------------------------


def _sign(secret: str) -> tuple[str, str]:
    """生成钉钉加签参数。

    返回 (timestamp, sign) 二元组。
    """
    timestamp = str(round(time.time() * 1000))
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
    if not secret:
        return webhook_url
    timestamp, sign = _sign(secret)
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


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
    url = _build_webhook_url(webhook_url, secret)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=msg_body)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("errcode") == 0:
                    return {"success": True, "message": "推送成功", "raw": body}
                return {
                    "success": False,
                    "message": f"钉钉返回错误: {body.get('errmsg', '未知')}",
                    "raw": body,
                }
            return {"success": False, "message": f"HTTP {resp.status_code}", "raw": {}}
    except httpx.TimeoutException:
        return {"success": False, "message": "请求超时", "raw": {}}
    except Exception as e:
        logger.exception("钉钉推送失败")
        return {"success": False, "message": f"请求失败: {str(e)[:200]}", "raw": {}}


async def send_text(
    db: AsyncSession,
    content: str,
    at_mobiles: list[str] | None = None,
) -> dict[str, Any]:
    """发送文本消息。"""
    cfg = await get_webhook_config(db)
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
                # 钉钉 markdown 不直接支持 media_id，需要用图片 URL
                # 暂时使用链接方式
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
        "*营销数据驾驶舱 · 自动推送*",
    ])

    title = f"营销数据驾驶舱 · {type_label}"
    text = "\n".join(lines)
    return title, text


def build_express_markdown(
    express_title: str,
    sections: list[dict],
    express_id: int,
    base_url: str = "",
) -> tuple[str, str]:
    """构造速递推送的 Markdown 消息。

    返回 (title, text) 二元组。
    """
    full_url = f"{base_url}/re/{express_id}" if base_url else f"/re/{express_id}"

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
        "*营销数据驾驶舱 · 每日速递*",
    ]

    title = "营销数据驾驶舱 · 每日速递"
    text = "\n".join(lines)
    return title, text
