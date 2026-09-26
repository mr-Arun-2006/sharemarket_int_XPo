from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps.auth import require_permission
from app.db.mongo import get_database
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    description: str = Field(default="", max_length=240)
    permissions: list[str] = Field(default_factory=list, max_length=100)

class RolePermissionsUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list, max_length=100)

class UserRoleUpdate(BaseModel):
    role: str = Field(min_length=2, max_length=40)

@router.get("/roles")
async def list_roles(_: dict = Depends(require_permission("admin.roles.manage"))):
    roles = await get_database().roles.find({}, {"_id": 0}).sort("name", 1).to_list(length=200)
    return {"roles": roles}

@router.post("/roles", status_code=201)
async def create_role(payload: RoleCreateRequest, current_user: dict = Depends(require_permission("admin.roles.manage"))):
    db = get_database()
    if await db.roles.find_one({"name": payload.name}):
        raise HTTPException(409, "Role already exists")
    role = {
        "name": payload.name,
        "description": payload.description,
        "permissions": sorted(set(payload.permissions)),
        "system": False,
    }
    await db.roles.insert_one(role)
    await record_audit("admin.role_created", user_id=current_user["user_id"], target_type="role", target_id=payload.name)
    return role

@router.patch("/roles/{role_name}")
async def update_role_permissions(role_name: str, payload: RolePermissionsUpdate, current_user: dict = Depends(require_permission("admin.roles.manage"))):
    db = get_database()
    role = await db.roles.find_one({"name": role_name})
    if not role:
        raise HTTPException(404, "Role not found")
    if role.get("system") and role_name == "admin":
        raise HTTPException(400, "The admin role cannot be customized here")
    await db.roles.update_one({"name": role_name}, {"$set": {"permissions": sorted(set(payload.permissions))}})
    await record_audit("admin.role_permissions_updated", user_id=current_user["user_id"], target_type="role", target_id=role_name)
    return {"status": "updated", "role": role_name, "permissions": sorted(set(payload.permissions))}

@router.get("/users")
async def list_users(_: dict = Depends(require_permission("admin.users.manage"))):
    users = await get_database().user.find(
        {},
        {"_id": 0, "user_id": 1, "email": 1, "role": 1, "email_verified": 1, "two_factor_enabled": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(length=500)
    return {"users": users}

@router.patch("/users/{user_id}/role")
async def update_user_role(user_id: str, payload: UserRoleUpdate, current_user: dict = Depends(require_permission("admin.users.manage"))):
    db = get_database()
    role = await db.roles.find_one({"name": payload.role})
    if not role:
        raise HTTPException(404, "Role not found")
    user = await db.user.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    await db.user.update_one({"user_id": user_id}, {"$set": {"role": payload.role, "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)}})
    await record_audit("admin.user_role_updated", user_id=current_user["user_id"], target_type="user", target_id=user_id, metadata={"role": payload.role})
    return {"status": "updated", "user_id": user_id, "role": payload.role}

@router.get("/audit")
async def audit(_: dict = Depends(require_permission("admin.audit.read"))):
    items = await get_database().audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    return {"events": items}
