from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, HTTPException, status

from app.db.mongo import get_database
from app.core.security import create_opaque_token, hash_password, hash_token, verify_password
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, VerifyRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

def _now():
    return datetime.now(timezone.utc)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    db = get_database()
    email = payload.email.lower()
    existing = await db.user.find_one({"email_normalized": email})
    if existing:
        raise HTTPException(409, "Account already exists")

    user_id = secrets.token_hex(16)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = _now()

    await db.user.insert_one({
        "user_id": user_id,
        "email": email,
        "email_normalized": email,
        "password_hash": hash_password(payload.password),
        "role": "user",
        "ai_language": "en",
        "email_verified": False,
        "two_factor_enabled": False,
        "created_at": now,
        "updated_at": now,
    })
    await db.auth_challenges.insert_one({
        "user_id": user_id,
        "email": email,
        "purpose": "email_verification",
        "otp_hash": hash_token(otp),
        "attempts": 0,
        "created_at": now,
        "expires_at": now + timedelta(minutes=10),
    })
    return {"status": "verification_required", "user_id": user_id, "development_otp": otp}

@router.post("/verify")
async def verify(payload: VerifyRequest):
    db = get_database()
    email = payload.email.lower()
    challenge = await db.auth_challenges.find_one({
        "email": email,
        "purpose": "email_verification",
        "expires_at": {"$gt": _now()},
    })
    if not challenge or not secrets.compare_digest(hash_token(payload.otp), challenge["otp_hash"]):
        raise HTTPException(400, "Invalid or expired verification code")

    await db.user.update_one(
        {"email_normalized": email},
        {"$set": {"email_verified": True, "updated_at": _now()}},
    )
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

    access = create_opaque_token()
    refresh = create_opaque_token()
    now = _now()
    await db.sessions.insert_one({
        "user_id": user["user_id"],
        "token_hash": hash_token(refresh),
        "access_token_hash": hash_token(access),
        "created_at": now,
        "last_used_at": now,
        "expires_at": now + timedelta(days=30),
        "revoked_at": None,
    })
    return AuthResponse(access_token=access, refresh_token=refresh)
