"""Role and permission definitions for management access control."""

from __future__ import annotations

from typing import Any

ROLES: dict[str, dict[str, Any]] = {
    "super_admin": {"label": "超级管理员", "permissions": ["*"]},
    "admin": {
        "label": "管理员",
        "permissions": [
            "dashboard:view",
            "dashboard:export",
            "reports:view",
            "reports:generate",
            "intelligence:view",
            "opportunities:view",
            "opportunities:manage",
            "management:view",
            "management:crawler",
            "management:llm",
            "management:users",
            "management:settings",
            "management:express",
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


def permissions_for_role(role: str | None) -> list[str]:
    """Return permissions for a role key."""

    role_def = ROLES.get(role or "viewer") or ROLES["viewer"]
    return list(role_def["permissions"])


def has_permission(user: dict[str, Any], permission: str) -> bool:
    """Check whether a user dict contains a permission."""

    permissions = user.get("permissions") or permissions_for_role(user.get("role"))
    return "*" in permissions or permission in permissions
