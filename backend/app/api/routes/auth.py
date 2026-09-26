from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import create_access_token, create_refresh_token, hash_password, hash_token, verify_password
from app.db.mongo import get_database
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, VerifyRequest
from app.api.deps.auth import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

def _now():
    return datetime.now(timezone.utc)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    db = get_database()
    email = payload.email.lower()
    if await db.user.find_one({"email_normalized": email}):
        raise HTTPException(409, "Account already exists")

    user_id = secrets.token_hex(16)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = _now()
    await db.user.insert_one({
        "user_id": user_id, "email": email, "email_normalized": email,
        "password_hash": hash_password(payload.password), "role": "user",
        "ai_language": "en", "email_verified": False, "two_factor_enabled": False,
        "created_at": now, "updated_at": now,
    })
    await db.auth_challenges.insert_one({
        "user_id": user_id, "email": email, "purpose": "email_verification",
        "otp_hash": hash_token(otp), "attempts": 0, "created_at": now,
        "expires_at": now + timedelta(minutes=10),
    })
    response = {"status": "verification_required", "user_id": user_id}
    if __import__("app.core.config", fromlist=["settings"]).settings.app_env == "development":
        response["development_otp"] = otp
    return response

@router.post("/verify")
async def verify(payload: VerifyRequest):
    db = get_database()
    email = payload.email.lower()
    challenge = await db.auth_challenges.find_one({
        "email": email, "purpose": "email_verification", "expires_at": {"$gt": _now()},
    })
    if not challenge or not secrets.compare_digest(hash_token(payload.otp), challenge["otp_hash"]):
        raise HTTPException(400, "Invalid or expired verification code")
    await db.user.update_one({"email_normalized": email}, {"$set": {"email_verified": True, "updated_at": _now()}})
    await db.auth_challenges.delete_many({"user_id": challenge["user_id"], "purpose": "email_verification"})
    return {"status": "verified"}

@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    db = get_database()
    email = payload.email.lower()
    user = await db.user.find_one({"email_normalized": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("email_verified"):
        raise HTTPException(403, "Email verification required")

    session_id = secrets.token_hex(16)
    refresh = create_refresh_token()
    now = _now()
    await db.sessions.insert_one({
        "session_id": session_id, "user_id": user["user_id"], "role": user["role"],
        "token_hash": hash_token(refresh), "created_at": now, "last_used_at": now,
        "expires_at": now + timedelta(days=30), "revoked_at": None,
    })
    access = create_access_token(user["user_id"], user["role"], session_id)
    return AuthResponse(access_token=access, refresh_token=refresh)

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "role": current_user["role"],
        "ai_language": current_user.get("ai_language", "en"),
    }

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    db = get_database()
    await db.sessions.update_many(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    return {"status": "logged_out"}
