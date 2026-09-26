from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.mongo import get_database

bearer = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        claims = decode_access_token(credentials.credentials)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid or expired access token")

    db = get_database()
    user = await db.user.find_one({"user_id": claims["sub"]})
    if not user:
        raise HTTPException(401, "User session is invalid")

    session = await db.sessions.find_one({
        "session_id": claims["sid"],
        "user_id": user["user_id"],
        "revoked_at": None,
        "expires_at": {"$gt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)},
    })
    if not session:
        raise HTTPException(401, "Session has been revoked or expired")
    return user

def require_permission(permission: str):
    async def dependency(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") == "admin":
            return current_user

        role = await get_database().roles.find_one({"name": current_user.get("role")})
        permissions = set(role.get("permissions", [])) if role else set()
        if "*" not in permissions and permission not in permissions:
            raise HTTPException(403, "Permission denied")
        return current_user
    return dependency
