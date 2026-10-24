"""Permissions operations."""
from __future__ import annotations

from typing import Any
import json

from fastapi import HTTPException, Request

from . import state
from .repository import audit_connection


def access_tree() -> dict[str, list[dict[str, Any]]]:
    with state.audit_lock, audit_connection() as connection:
        roles = [dict(row) for row in connection.execute("SELECT * FROM roles ORDER BY id").fetchall()]
        users = [dict(row) for row in connection.execute("SELECT * FROM users ORDER BY id").fetchall()]
    return {"roles": [{**role, "permissions": json.loads(role["permissions"])} for role in roles], "users": users}


def require_permission(request: Request, permission: str) -> dict[str, Any]:
    operator_id = request.headers.get("X-Operator-Id", "super-admin")
    tree = access_tree()
    user = next((item for item in tree["users"] if item["id"] == operator_id), None)
    if not user:
        raise HTTPException(status_code=403, detail="Unknown operator")
    role = next((item for item in tree["roles"] if item["id"] == user["role_id"]), None)
    if not role or ("*" not in role["permissions"] and permission not in role["permissions"]):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
    return user
