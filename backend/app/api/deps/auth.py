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
    })
    if not session:
        raise HTTPException(401, "Session has been revoked")
    return user
