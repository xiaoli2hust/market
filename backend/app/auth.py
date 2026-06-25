"""认证工具模块。

提供：
- bcrypt 密码哈希与校验
- JWT access_token 生成与解析
- FastAPI 依赖：当前用户、上传接口 API Key
- 报告页面时效 Token（用于公开报告链接）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import jwt
import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import APIKeyRecord, SystemUser
from .permissions import has_permission, permissions_for_role
from .secret_store import verify_api_key_hash

# OAuth2 密码模式：tokenUrl 指向登录接口，便于 Swagger 一键授权调试。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

PASSWORD_MIN_LENGTH = 8


def get_password_hash(password: str) -> str:
    """生成 bcrypt 密码哈希。"""

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# 兼容旧调用名
hash_password = get_password_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否一致。"""

    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        return False


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


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session_token: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """FastAPI 依赖：返回当前登录用户的 JWT 声明。

    若 token 缺失或无效，抛出 401。
    """

    token = token or session_token
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
    username = str(payload.get("sub") or "")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        await db.execute(select(SystemUser).where(SystemUser.username == username))
    ).scalar_one_or_none()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用",
            )
        return {
            "id": user.id,
            "sub": user.username,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name or user.username,
            "permissions": permissions_for_role(user.role),
        }

    # Bootstrap compatibility: allow the legacy env admin token before the
    # default admin row has been materialized.
    if username == settings.ADMIN_USERNAME and payload.get("role") in {"admin", "super_admin"}:
        role = payload.get("role") or "super_admin"
        return {
            **payload,
            "username": username,
            "role": role,
            "permissions": permissions_for_role(role),
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="user no longer exists",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_permission(permission: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """FastAPI dependency factory that enforces a named permission."""

    async def _require_permission(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission}",
            )
        return current_user

    return _require_permission


async def verify_api_key(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """FastAPI 依赖：校验上传接口的 API Key。

    要求 Authorization Header 格式为 ``Bearer {UPLOAD_API_KEY}``，
    不匹配则抛 403。
    """

    legacy_key = _active_legacy_upload_key(settings.UPLOAD_API_KEY)
    if not legacy_key:
        key_count = (
            await db.execute(select(APIKeyRecord.id).where(APIKeyRecord.is_active.is_(True)).limit(1))
        ).scalar_one_or_none()
        if key_count is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="api key not configured",
            )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid api key",
        )

    if legacy_key and token == legacy_key:
        return True

    records = (
        await db.execute(select(APIKeyRecord).where(APIKeyRecord.is_active.is_(True)))
    ).scalars().all()
    for record in records:
        if verify_api_key_hash(token, record.key_value):
            return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="invalid api key",
    )


def _active_legacy_upload_key(value: str | None) -> str | None:
    """Return a configured legacy upload key, ignoring known placeholder values."""

    key = (value or "").strip()
    if not key or key in {"change-me", "change-me-in-production", "please-change-me"}:
        return None
    return key


def verify_upload_api_key(api_key: str | None) -> bool:
    """旧式 API Key 工具函数：仅做字符串比对，保留向前兼容。"""

    legacy_key = _active_legacy_upload_key(settings.UPLOAD_API_KEY)
    if not api_key or not legacy_key:
        return False
    return api_key == legacy_key


# ---------- 公开页面时效 Token ----------

_REPORT_TOKEN_TYPE = "report"
_EXPRESS_TOKEN_TYPE = "express"


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


def create_express_token(express_id: int, expires_days: int = 7) -> str:
    """为每日速递生成短期分享 Token。

    速递通常用于当天或近期同步，默认 7 天有效，避免公开链接暴露可枚举的数字 ID。
    """

    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=expires_days)
    payload: dict[str, Any] = {
        "type": _EXPRESS_TOKEN_TYPE,
        "express_id": int(express_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_express_token(token: str) -> int | None:
    """校验速递分享 Token，成功返回 express_id，失败返回 None。"""

    payload = decode_token(token)
    if not payload:
        return None
    if payload.get("type") != _EXPRESS_TOKEN_TYPE:
        return None
    express_id = payload.get("express_id")
    if not isinstance(express_id, int):
        return None
    return express_id
