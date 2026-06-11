"""认证相关路由：管理者登录与当前用户信息。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import create_access_token, get_current_user
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    username: str
    user: dict | None = None


class UserInfo(BaseModel):
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """管理者登录。

    MVP 阶段：账密直接来自环境变量（明文比对），暂不引入用户表。
    """

    if (
        request.username != settings.ADMIN_USERNAME
        or request.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token({"sub": request.username, "role": "admin"})
    user_info = {"id": 0, "name": request.username, "role": "admin", "department": "总部"}
    return LoginResponse(token=token, username=request.username, user=user_info)


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> UserInfo:
    """获取当前登录用户信息。"""

    return UserInfo(
        username=current_user.get("sub", ""),
        role=current_user.get("role", "admin"),
    )
