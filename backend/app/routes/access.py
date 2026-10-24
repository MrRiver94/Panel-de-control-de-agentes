"""Routes access operations."""
from __future__ import annotations

from typing import Any
import json

from fastapi import APIRouter, HTTPException, Request

from .. import state
from ..models import RoleUpdate, UserUpdate
from ..permissions import access_tree, require_permission
from ..repository import audit_connection, save_activity_event

router = APIRouter()


@router.get("/api/access/tree")
def get_access_tree(request: Request) -> dict[str, list[dict[str, Any]]]:
    require_permission(request, "access.manage")
    return access_tree()


@router.post("/api/access/roles")
def create_role(update: RoleUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    role_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-")
    if not role_id:
        raise HTTPException(status_code=422, detail="Invalid role name")
    with state.audit_lock, audit_connection() as connection:
        connection.execute("INSERT INTO roles VALUES (?, ?, ?)", (role_id, update.name.strip().upper(), json.dumps(update.permissions)))
    save_activity_event("access", "ACCESO", "role_created", f"Rol {role_id} creado.")
    return access_tree()


@router.post("/api/access/users")
def create_user(update: UserUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    user_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-")
    with state.audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (update.role_id,)).fetchone():
            raise HTTPException(status_code=422, detail="Unknown role")
        connection.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, update.name.strip(), update.role_id))
    save_activity_event("access", "ACCESO", "user_created", f"Usuario {user_id} creado con rol {update.role_id}.")
    return access_tree()


@router.post("/api/access/roles/{role_id}")
def update_role(role_id: str, update: RoleUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if role_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin role is protected")
    with state.audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Unknown role")
        connection.execute("UPDATE roles SET name=?, permissions=? WHERE id=?", (update.name.strip().upper(), json.dumps(update.permissions), role_id))
    save_activity_event("access", "ACCESO", "role_updated", f"Rol {role_id} actualizado.")
    return access_tree()


@router.delete("/api/access/roles/{role_id}")
def delete_role(role_id: str, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if role_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin role is protected")
    with state.audit_lock, audit_connection() as connection:
        if connection.execute("SELECT 1 FROM users WHERE role_id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=400, detail="Move users before deleting this role")
        if not connection.execute("DELETE FROM roles WHERE id=?", (role_id,)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown role")
    save_activity_event("access", "ACCESO", "role_deleted", f"Rol {role_id} eliminado.")
    return access_tree()


@router.post("/api/access/users/{user_id}")
def update_user(user_id: str, update: UserUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if user_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin user is protected")
    with state.audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (update.role_id,)).fetchone():
            raise HTTPException(status_code=422, detail="Unknown role")
        if not connection.execute("UPDATE users SET name=?, role_id=? WHERE id=?", (update.name.strip(), update.role_id, user_id)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown user")
    save_activity_event("access", "ACCESO", "user_updated", f"Usuario {user_id} actualizado.")
    return access_tree()


@router.delete("/api/access/users/{user_id}")
def delete_user(user_id: str, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if user_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin user is protected")
    with state.audit_lock, audit_connection() as connection:
        if not connection.execute("DELETE FROM users WHERE id=?", (user_id,)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown user")
    save_activity_event("access", "ACCESO", "user_deleted", f"Usuario {user_id} eliminado.")
    return access_tree()
