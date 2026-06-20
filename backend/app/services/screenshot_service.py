"""Playwright 截图服务。

将 HTML 内容渲染为高清 PNG 长图，用于钉钉速递推送。
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 截图存放目录
SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent.parent / "screenshots"


def _ensure_screenshots_dir() -> Path:
    """确保截图目录存在。"""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOTS_DIR


async def capture_html_to_image(
    html_content: str,
    output_path: str | None = None,
    width: int = 390,
    device_scale_factor: int = 2,
) -> str:
    """将 HTML 内容截图为高清 PNG 长图。

    Args:
        html_content: 完整的 HTML 文档字符串（需包含 <html><body> 等）
        output_path: 输出文件路径。如果为 None，自动生成到 screenshots/ 目录。
        width: 视口宽度（像素），默认 390 适合手机查看。
        device_scale_factor: 设备像素比，2 = Retina 清晰度。

    Returns:
        截图文件的绝对路径。

    Raises:
        RuntimeError: Playwright 未安装或截图失败。
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装。请执行：pip install playwright && playwright install chromium"
        )

    # 自动生成输出路径
    if not output_path:
        screenshots_dir = _ensure_screenshots_dir()
        import time
        output_path = str(screenshots_dir / f"screenshot_{int(time.time())}.png")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": width, "height": 800},
                device_scale_factor=device_scale_factor,
            )
            page = await context.new_page()

            # 设置 HTML 内容
            await page.set_content(
                html_content,
                wait_until="networkidle",
            )

            # 等待字体和图片加载
            await page.wait_for_timeout(500)

            # 全页截图
            await page.screenshot(
                path=output_path,
                full_page=True,
                type="png",
            )

            file_size = os.path.getsize(output_path)
            logger.info("截图完成: %s (%.1f KB)", output_path, file_size / 1024)
            return output_path

        finally:
            await browser.close()


async def capture_url_to_image(
    url: str,
    output_path: str | None = None,
    width: int = 390,
    device_scale_factor: int = 2,
    wait_seconds: int = 2,
) -> str:
    """将 URL 页面截图为高清 PNG 长图。

    用于截取在线页面（如报告公开链接 / 速递公开链接）。

    Args:
        url: 要截取的 URL
        output_path: 输出文件路径
        width: 视口宽度
        device_scale_factor: 设备像素比
        wait_seconds: 页面加载后等待秒数（等待异步渲染完成）

    Returns:
        截图文件的绝对路径。
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装。请执行：pip install playwright && playwright install chromium"
        )

    if not output_path:
        screenshots_dir = _ensure_screenshots_dir()
        import time
        output_path = str(screenshots_dir / f"screenshot_{int(time.time())}.png")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": width, "height": 800},
                device_scale_factor=device_scale_factor,
            )
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(wait_seconds * 1000)

            await page.screenshot(
                path=output_path,
                full_page=True,
                type="png",
            )

            file_size = os.path.getsize(output_path)
            logger.info("URL 截图完成: %s → %s (%.1f KB)", url, output_path, file_size / 1024)
            return output_path

        finally:
            await browser.close()


def get_screenshot_path(express_id: int) -> str:
    """获取指定速递的截图存放路径（不创建文件）。"""
    screenshots_dir = _ensure_screenshots_dir()
    return str(screenshots_dir / f"express_{express_id}.png")


def screenshot_exists(express_id: int) -> bool:
    """检查指定速递的截图是否已存在（缓存复用）。"""
    path = get_screenshot_path(express_id)
    return os.path.isfile(path)
