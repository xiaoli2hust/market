"""认证工具模块。

提供：
- bcrypt 密码哈希与校验
- JWT access_token 生成与解析
- FastAPI 依赖：当前用户、上传接口 API Key
- 报告页面时效 Token（用于公开报告链接）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from .config import settings

# OAuth2 密码模式：tokenUrl 指向登录接口，便于 Swagger 一键授权调试。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# bcrypt 密码哈希上下文，向前兼容 deprecated 算法。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """生成 bcrypt 密码哈希。"""

    return pwd_context.hash(password)


# 兼容旧调用名
hash_password = get_password_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否一致。"""

    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """生成 JWT access_token。

    Args:
        data: payload 内容，至少包含 sub（用户名），通常还有 role。
        expires_delta: 自定义过期时间，默认使用 settings.JWT_EXPIRE_HOURS。
    """

    now = datetime.now(tz=timezone.utc)
    expire = now + (expires_delta or timedelta(hours=settings.JWT_EXPIRE_HOURS))
    payload: dict[str, Any] = dict(data)
    payload.update(
        {
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """解析 JWT，失败返回 None（不抛异常）。"""

    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT，无效时抛 401（保留旧接口）。"""

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    """FastAPI 依赖：返回当前登录用户的 JWT 声明。

    若 token 缺失或无效，抛出 401。
    """

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def verify_api_key(authorization: str = Header(...)) -> bool:
    """FastAPI 依赖：校验上传接口的 API Key。

    要求 Authorization Header 格式为 ``Bearer {UPLOAD_API_KEY}``，
    不匹配则抛 403。
    """

    expected = settings.UPLOAD_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="upload api key not configured",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid api key",
        )
    return True


def verify_upload_api_key(api_key: str | None) -> bool:
    """旧式 API Key 工具函数：仅做字符串比对，保留向前兼容。"""

    if not api_key or not settings.UPLOAD_API_KEY:
        return False
    return api_key == settings.UPLOAD_API_KEY


# ---------- 报告页面时效 Token ----------

_REPORT_TOKEN_TYPE = "report"


def create_report_token(report_id: int, expires_days: int = 30) -> str:
    """为报告页面生成时效 Token。

    报告链接通常对外公开传播，使用独立 payload（type=report）与默认 30 天过期，
    避免与登录态 token 混淆。
    """

    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=expires_days)
    payload: dict[str, Any] = {
        "type": _REPORT_TOKEN_TYPE,
        "report_id": int(report_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_report_token(token: str) -> int | None:
    """校验报告 Token，成功返回 report_id，失败返回 None。"""

    payload = decode_token(token)
    if not payload:
        return None
    if payload.get("type") != _REPORT_TOKEN_TYPE:
        return None
    report_id = payload.get("report_id")
    if not isinstance(report_id, int):
        return None
    return report_id
