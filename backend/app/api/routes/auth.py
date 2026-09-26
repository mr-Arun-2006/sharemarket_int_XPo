from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password, hash_token, verify_password
from app.core.totp import build_otpauth_url, generate_secret, verify_totp
from app.db.mongo import get_database
from app.schemas.auth import (
    AuthResponse, LoginRequest, LoginResponse, RefreshRequest, RegisterRequest,
    TwoFactorCodeRequest, TwoFactorVerifyRequest, VerifyRequest,
)
from app.api.deps.auth import get_current_user
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

def _now():
    return datetime.now(timezone.utc)

async def _issue_session(db, user: dict):
    session_id = secrets.token_hex(16)
    refresh = create_refresh_token()
    now = _now()
    await db.sessions.insert_one({
        "session_id": session_id,
        "user_id": user["user_id"],
        "role": user["role"],
        "token_hash": hash_token(refresh),
        "created_at": now,
        "last_used_at": now,
        "expires_at": now + timedelta(days=settings.refresh_token_days),
        "revoked_at": None,
    })
    access = create_access_token(user["user_id"], user["role"], session_id)
    return AuthResponse(access_token=access, refresh_token=refresh)

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
    await record_audit("auth.register", user_id=user_id, target_type="user", target_id=user_id)
    response = {"status": "verification_required", "user_id": user_id}
    if settings.app_env == "development":
        response["development_otp"] = otp
    return response

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
    await record_audit("auth.verify_email", user_id=challenge["user_id"], target_type="user", target_id=challenge["user_id"])
    return {"status": "verified"}

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    db = get_database()
    email = payload.email.lower()
    user = await db.user.find_one({"email_normalized": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("email_verified"):
        raise HTTPException(403, "Email verification required")

    if user.get("two_factor_enabled"):
        challenge_id = secrets.token_urlsafe(32)
        await db.auth_challenges.insert_one({
            "challenge_id": challenge_id,
            "user_id": user["user_id"],
            "purpose": "login_2fa",
            "attempts": 0,
            "created_at": _now(),
            "expires_at": _now() + timedelta(minutes=5),
        })
        return LoginResponse(status="two_factor_required", challenge_id=challenge_id, requires_2fa=True)

    tokens = await _issue_session(db, user)
    await record_audit("auth.login", user_id=user["user_id"], target_type="session")
    return LoginResponse(status="authenticated", access_token=tokens.access_token, refresh_token=tokens.refresh_token)

@router.post("/2fa/verify-login", response_model=AuthResponse)
async def verify_login_2fa(payload: TwoFactorCodeRequest):
    db = get_database()
    challenge = await db.auth_challenges.find_one({
        "challenge_id": payload.challenge_id,
        "purpose": "login_2fa",
        "expires_at": {"$gt": _now()},
    })
    if not challenge:
        raise HTTPException(400, "Invalid or expired two-factor challenge")

    user = await db.user.find_one({"user_id": challenge["user_id"]})
    if not user or not user.get("two_factor_enabled") or not user.get("two_factor_secret"):
        raise HTTPException(400, "Two-factor authentication is not configured")

    if challenge.get("attempts", 0) >= 5 or not verify_totp(user["two_factor_secret"], payload.code):
        await db.auth_challenges.update_one({"_id": challenge["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(401, "Invalid two-factor code")

    await db.auth_challenges.delete_one({"_id": challenge["_id"]})
    tokens = await _issue_session(db, user)
    await record_audit("auth.login_2fa", user_id=user["user_id"], target_type="session")
    return tokens

@router.post("/2fa/setup")
async def setup_2fa(current_user: dict = Depends(get_current_user)):
    if current_user.get("two_factor_enabled"):
        raise HTTPException(409, "Two-factor authentication is already enabled")
    secret = generate_secret()
    await get_database().user.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"two_factor_pending_secret": secret, "updated_at": _now()}},
    )
    return {
        "secret": secret,
        "otpauth_url": build_otpauth_url(secret, current_user["email"]),
    }

@router.post("/2fa/enable")
async def enable_2fa(payload: TwoFactorVerifyRequest, current_user: dict = Depends(get_current_user)):
    db = get_database()
    secret = current_user.get("two_factor_pending_secret")
    if not secret or not verify_totp(secret, payload.code):
        raise HTTPException(400, "Invalid verification code")
    await db.user.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"two_factor_enabled": True, "two_factor_secret": secret, "updated_at": _now()},
         "$unset": {"two_factor_pending_secret": ""}},
    )
    await record_audit("auth.2fa_enabled", user_id=current_user["user_id"], target_type="user", target_id=current_user["user_id"])
    return {"status": "enabled"}

@router.post("/2fa/disable")
async def disable_2fa(payload: TwoFactorVerifyRequest, current_user: dict = Depends(get_current_user)):
    secret = current_user.get("two_factor_secret")
    if not current_user.get("two_factor_enabled") or not secret or not verify_totp(secret, payload.code):
        raise HTTPException(400, "Invalid verification code")
    db = get_database()
    await db.user.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"two_factor_enabled": False, "updated_at": _now()},
        "$unset": {"two_factor_secret": "", "two_factor_pending_secret": ""}},
    )
    await record_audit("auth.2fa_disabled", user_id=current_user["user_id"], target_type="user", target_id=current_user["user_id"])
    return {"status": "disabled"}

@router.post("/refresh", response_model=AuthResponse)
async def refresh(payload: RefreshRequest):
    db = get_database()
    session = await db.sessions.find_one({
        "token_hash": hash_token(payload.refresh_token),
        "revoked_at": None,
        "expires_at": {"$gt": _now()},
    })
    if not session:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = await db.user.find_one({"user_id": session["user_id"]})
    if not user:
        raise HTTPException(401, "User session is invalid")
    await db.sessions.update_one({"_id": session["_id"]}, {"$set": {"revoked_at": _now(), "last_used_at": _now()}})
    return await _issue_session(db, user)

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "role": current_user["role"],
        "ai_language": current_user.get("ai_language", "en"),
        "two_factor_enabled": bool(current_user.get("two_factor_enabled", False)),
    }

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    db = get_database()
    await db.sessions.update_many(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    await record_audit("auth.logout", user_id=current_user["user_id"], target_type="user", target_id=current_user["user_id"])
    return {"status": "logged_out"}

@router.post("/logout-all")
async def logout_all(current_user: dict = Depends(get_current_user)):
    db = get_database()
    result = await db.sessions.update_many(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    await record_audit("auth.logout_all", user_id=current_user["user_id"], target_type="user", target_id=current_user["user_id"])
    return {"status": "logged_out", "sessions_revoked": result.modified_count}
