"""Shared input validation helpers."""

from __future__ import annotations

from fastapi import HTTPException
from urllib.parse import urlparse


def validate_http_url(value: str | None, field_name: str, *, allow_empty: bool = False) -> str | None:
    """Validate and normalize an HTTP/HTTPS URL string."""

    text = (value or "").strip()
    if not text:
        if allow_empty:
            return None
        raise HTTPException(status_code=400, detail=f"{field_name} 不能为空")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail=f"{field_name} 必须是有效的 HTTP/HTTPS 地址")
    return text.rstrip("/")
