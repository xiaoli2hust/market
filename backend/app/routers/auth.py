"""认证相关路由：管理者登录与当前用户信息。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    PASSWORD_MIN_LENGTH,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from ..config import settings
from ..database import get_db
from ..models import SystemUser
from ..permissions import permissions_for_role

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
_LOGIN_MAX_FAILURES = 5
_login_failures: dict[str, list[datetime]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    username: str
    user: dict | None = None


class UserInfo(BaseModel):
    id: int | None = None
    username: str
    name: str | None = None
    role: str
    permissions: list[str] = []
    department: str | None = None
    security_warnings: list[str] = []
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _login_failure_key(request: Request, username: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{username.lower()}"


def _recent_login_failures(key: str, now: datetime) -> list[datetime]:
    cutoff = now - _LOGIN_FAILURE_WINDOW
    recent = [item for item in _login_failures.get(key, []) if item > cutoff]
    if recent:
        _login_failures[key] = recent
    else:
        _login_failures.pop(key, None)
    return recent


def _assert_login_allowed(key: str, now: datetime) -> None:
    if len(_recent_login_failures(key, now)) >= _LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )


def _record_failed_login(key: str, now: datetime) -> None:
    recent = _recent_login_failures(key, now)
    recent.append(now)
    _login_failures[key] = recent


def _clear_failed_login(key: str) -> None:
    _login_failures.pop(key, None)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """用户登录，优先使用管理中心维护的用户表。"""

    username = payload.username.strip()
    now = datetime.now(tz=timezone.utc)
    failure_key = _login_failure_key(http_request, username)
    _assert_login_allowed(failure_key, now)
    user = (
        await db.execute(select(SystemUser).where(SystemUser.username == username))
    ).scalar_one_or_none()

    if not user:
        user_count = (await db.execute(select(func.count(SystemUser.id)))).scalar_one() or 0
        if (
            user_count == 0
            and username == settings.ADMIN_USERNAME
            and payload.password == settings.ADMIN_PASSWORD
        ):
            user = SystemUser(
                username=username,
                password_hash=get_password_hash(payload.password),
                role="super_admin",
                display_name=username,
                is_active=True,
                last_login_at=now,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
        else:
            _record_failed_login(failure_key, now)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

    if not user.is_active:
        _record_failed_login(failure_key, now)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    if not verify_password(payload.password, user.password_hash):
        _record_failed_login(failure_key, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    _clear_failed_login(failure_key)
    user.last_login_at = now
    token = create_access_token({"sub": user.username, "role": user.role, "uid": user.id})
    security_warnings = []
    if (
        user.username == settings.ADMIN_USERNAME
        and settings.ADMIN_PASSWORD == "admin123"
        and verify_password(settings.ADMIN_PASSWORD, user.password_hash)
    ):
        security_warnings.append("default_admin_password")

    user_info = {
        "id": user.id,
        "name": user.display_name or user.username,
        "username": user.username,
        "role": user.role,
        "permissions": permissions_for_role(user.role),
        "department": "管理中心",
        "security_warnings": security_warnings,
        "must_change_password": "default_admin_password" in security_warnings,
    }
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )
    return LoginResponse(token=token, username=user.username, user=user_info)


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> UserInfo:
    """获取当前登录用户信息。"""

    username = str(current_user.get("username") or current_user.get("sub") or "")
    return UserInfo(
        id=current_user.get("id"),
        username=username,
        name=current_user.get("display_name") or username,
        role=current_user.get("role", "admin"),
        permissions=current_user.get("permissions") or permissions_for_role(current_user.get("role", "admin")),
        department="管理中心",
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """退出登录并清理浏览器会话 Cookie。"""

    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """当前登录用户修改自己的密码。"""

    username = str(current_user.get("username") or current_user.get("sub") or "")
    user = (
        await db.execute(select(SystemUser).where(SystemUser.username == username))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if len(payload.new_password.strip()) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=400, detail=f"新密码长度至少{PASSWORD_MIN_LENGTH}位")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    user.password_hash = get_password_hash(payload.new_password)
    user.last_login_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return {"status": "ok"}
