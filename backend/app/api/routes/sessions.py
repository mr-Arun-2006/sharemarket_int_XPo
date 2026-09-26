from fastapi import APIRouter, Depends, HTTPException

from app.api.deps.auth import get_current_user
from app.db.mongo import get_database
from app.core.security import hash_token

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

@router.get("")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    db = get_database()
    cursor = db.sessions.find(
        {"user_id": current_user["user_id"]},
        {
            "_id": 0,
            "session_id": 1,
            "created_at": 1,
            "last_used_at": 1,
            "expires_at": 1,
            "revoked_at": 1,
        },
    ).sort("created_at", -1)
    return {"sessions": await cursor.to_list(length=100)}

@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    result = await db.sessions.update_one(
        {
            "session_id": session_id,
            "user_id": current_user["user_id"],
            "revoked_at": None,
        },
        {"$set": {"revoked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Session not found")
    return {"status": "revoked", "session_id": session_id}
