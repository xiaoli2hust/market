"""用户管理路由。

提供系统用户的 CRUD、角色管理、密码重置等接口。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
import bcrypt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import SystemUser, OperationLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system-users", tags=["system-users"])

# 角色定义
ROLES = {
    "super_admin": {"label": "超级管理员", "permissions": ["*"]},
    "admin": {
        "label": "管理员",
        "permissions": [
            "dashboard:view", "dashboard:export",
            "reports:view", "reports:generate",
            "intelligence:view",
            "opportunities:view",
            "management:view", "management:crawler", "management:express",
        ],
    },
    "viewer": {
        "label": "查看者",
        "permissions": [
            "dashboard:view",
            "intelligence:view",
            "opportunities:view",
        ],
    },
}


# ---------------------------------------------------------------------------
# 用户列表
# ---------------------------------------------------------------------------


@router.get("/")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """用户列表。"""
    total = (await db.execute(select(func.count(SystemUser.id)))).scalar_one() or 0

    rows = (await db.execute(
        select(SystemUser)
        .order_by(SystemUser.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "total": int(total),
        "items": [_user_to_dict(u) for u in rows],
    }


# ---------------------------------------------------------------------------
# 创建用户
# ---------------------------------------------------------------------------


@router.post("/")
async def create_user(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """创建系统用户。"""
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    role = payload.get("role", "viewer")

    if not username or not password:
        raise HTTPException(400, "用户名和密码不能为空")
    if role not in ROLES:
        raise HTTPException(400, f"无效角色: {role}")

    # 检查重复
    existing = (await db.execute(
        select(SystemUser).where(SystemUser.username == username)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"用户名 '{username}' 已存在")

    user = SystemUser(
        username=username,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        role=role,
        display_name=payload.get("display_name", username),
        is_active=payload.get("is_active", True),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # 记录日志
    _log_operation(db, _user, "create_user", username)

    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# 编辑用户
# ---------------------------------------------------------------------------


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """编辑用户信息。"""
    user = (await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")

    if "role" in payload and payload["role"] in ROLES:
        user.role = payload["role"]
    if "display_name" in payload:
        user.display_name = payload["display_name"]
    if "is_active" in payload:
        user.is_active = payload["is_active"]

    await db.flush()
    await db.refresh(user)
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# 重置密码
# ---------------------------------------------------------------------------


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    payload: dict[str, str],
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """重置用户密码。"""
    user = (await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")

    new_password = payload.get("password", "").strip()
    if not new_password or len(new_password) < 6:
        raise HTTPException(400, "密码长度至少6位")

    user.password_hash = pwd_context.hash(new_password)
    _log_operation(db, _user, "reset_password", user.username)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 删除用户
# ---------------------------------------------------------------------------


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除用户。"""
    user = (await db.execute(
        select(SystemUser).where(SystemUser.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.username == "admin":
        raise HTTPException(400, "不能删除默认管理员账号")

    _log_operation(db, _user, "delete_user", user.username)
    await db.delete(user)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 角色列表
# ---------------------------------------------------------------------------


@router.get("/roles")
async def list_roles(
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """角色列表及权限矩阵。"""
    return [
        {"key": key, "label": val["label"], "permissions": val["permissions"]}
        for key, val in ROLES.items()
    ]


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------


@router.get("/logs")
async def get_operation_logs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取操作日志。"""
    total = (await db.execute(select(func.count(OperationLog.id)))).scalar_one() or 0
    rows = (await db.execute(
        select(OperationLog)
        .order_by(OperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "total": int(total),
        "items": [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "target": r.target,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_to_dict(u: SystemUser) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "role_label": ROLES.get(u.role, {}).get("label", u.role),
        "display_name": u.display_name or u.username,
        "is_active": u.is_active,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _log_operation(db: AsyncSession, current_user: dict, action: str, target: str):
    """记录操作日志（不阻塞主流程）。"""
    log = OperationLog(
        username=current_user.get("sub", "unknown"),
        action=action,
        target=target,
    )
    db.add(log)
