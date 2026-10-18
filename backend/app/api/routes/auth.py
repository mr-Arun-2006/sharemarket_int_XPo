from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from pymongo import ReturnDocument
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.totp import build_otpauth_url, generate_secret, verify_totp
from app.core.config import settings
from app.db.mongo import get_database
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TwoFactorCodeRequest,
    TwoFactorVerifyRequest,
    VerifyRequest,
    EmailRequest,
)
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_rate_limit, rate_limit
from app.services.audit import record_audit
from app.services.email_delivery import send_verification_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_refresh_cookie(response: Response, token: str) -> None:
    kwargs = {
        "key": settings.auth_cookie_name,
        "value": token,
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite.lower(),
        "max_age": settings.refresh_token_days * 24 * 60 * 60,
        "path": "/api/v1/auth",
    }
    if settings.auth_cookie_domain:
        kwargs["domain"] = settings.auth_cookie_domain
    response.set_cookie(**kwargs)


def _clear_refresh_cookie(response: Response) -> None:
    kwargs = {
        "key": settings.auth_cookie_name,
        "path": "/api/v1/auth",
    }
    if settings.auth_cookie_domain:
        kwargs["domain"] = settings.auth_cookie_domain
    response.delete_cookie(**kwargs)


async def _issue_session(db, user: dict, response: Response) -> AuthResponse:
    session_id = secrets.token_hex(16)
    refresh = create_refresh_token()
    now = _now()
    await db.sessions.insert_one(
        {
            "session_id": session_id,
            "user_id": user["user_id"],
            "role": user["role"],
            "token_hash": hash_token(refresh),
            "created_at": now,
            "last_used_at": now,
            "expires_at": now + timedelta(days=settings.refresh_token_days),
            "revoked_at": None,
        }
    )
    _set_refresh_cookie(response, refresh)
    access = create_access_token(user["user_id"], user["role"], session_id)
    return AuthResponse(access_token=access)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit("auth.register", 5, 900)],
)
async def register(payload: RegisterRequest):
    db = get_database()
    email = str(payload.email).lower()
    if await db.user.find_one({"email_normalized": email}):
        raise HTTPException(409, "Account already exists")

    user_id = secrets.token_hex(16)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = _now()
    try:
        await db.user.insert_one(
            {
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
            }
        )
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Account already exists") from exc
    await db.auth_challenges.insert_one(
        {
            "user_id": user_id,
            "email": email,
            "purpose": "email_verification",
            "otp_hash": hash_token(otp),
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=10),
        }
    )
    try:
        await send_verification_email(email, otp)
    except Exception as exc:
        await record_audit(
            "auth.verification_email_failed",
            user_id=user_id,
            target_type="user",
            target_id=user_id,
        )
        if settings.app_env.lower() == "production":
            await db.auth_challenges.delete_many(
                {"user_id": user_id, "purpose": "email_verification"}
            )
            raise HTTPException(503, "Email verification service is temporarily unavailable") from exc

    await record_audit(
        "auth.register",
        user_id=user_id,
        target_type="user",
        target_id=user_id,
    )
    response = {"status": "verification_required", "user_id": user_id}
    if settings.app_env.lower() == "development":
        response["development_otp"] = otp
    return response


@router.post("/verify", dependencies=[rate_limit("auth.verify", 10, 600)])
async def verify(payload: VerifyRequest):
    db = get_database()
    email = str(payload.email).lower()
    challenge = await db.auth_challenges.find_one_and_update(
        {
            "email": email,
            "purpose": "email_verification",
            "expires_at": {"$gt": _now()},
            "attempts": {"$lt": 5},
        },
        {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not challenge or not secrets.compare_digest(
        hash_token(payload.otp), challenge["otp_hash"]
    ):
        raise HTTPException(400, "Invalid or expired verification code")

    await db.user.update_one(
        {"email_normalized": email},
        {"$set": {"email_verified": True, "updated_at": _now()}},
    )
    await db.auth_challenges.delete_many(
        {"user_id": challenge["user_id"], "purpose": "email_verification"}
    )
    await record_audit(
        "auth.verify_email",
        user_id=challenge["user_id"],
        target_type="user",
        target_id=challenge["user_id"],
    )
    return {"status": "verified"}


@router.post(
    "/resend-verification",
    dependencies=[rate_limit("auth.resend_verification", 3, 900)],
)
async def resend_verification(payload: EmailRequest):
    db = get_database()
    email = str(payload.email).lower()
    user = await db.user.find_one(
        {"email_normalized": email},
        {"_id": 0, "user_id": 1, "email_verified": 1},
    )

    # Return the same response for unknown addresses to avoid account enumeration.
    response = {"status": "verification_sent"}
    if not user or user.get("email_verified"):
        return response

    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = _now()
    await db.auth_challenges.delete_many(
        {"user_id": user["user_id"], "purpose": "email_verification"}
    )
    await db.auth_challenges.insert_one(
        {
            "user_id": user["user_id"],
            "email": email,
            "purpose": "email_verification",
            "otp_hash": hash_token(otp),
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=10),
        }
    )
    try:
        await send_verification_email(email, otp)
    except Exception as exc:
        if settings.app_env.lower() == "development":
            response["development_otp"] = otp
            return response
        await db.auth_challenges.delete_many(
            {"user_id": user["user_id"], "purpose": "email_verification"}
        )
        raise HTTPException(503, "Email verification service is temporarily unavailable") from exc

    return response


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[rate_limit("auth.login", 10, 60)],
)
async def login(payload: LoginRequest, response: Response):
    db = get_database()
    email = str(payload.email).lower()
    user = await db.user.find_one({"email_normalized": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        # Add a per-account failure bucket so distributed attempts against one
        # account cannot bypass the existing per-IP limit. HMAC prevents raw
        # email addresses from being stored in the rate-limit collection.
        account_key = hmac.new(
            settings.jwt_secret.encode(),
            email.encode(),
            hashlib.sha256,
        ).hexdigest()
        await enforce_rate_limit(
            "auth.login.account_failure",
            f"email:{account_key}",
            10,
            900,
        )
        raise HTTPException(401, "Invalid email or password")
    if not user.get("email_verified"):
        raise HTTPException(403, "Email verification required")

    if user.get("two_factor_enabled"):
        challenge_id = secrets.token_urlsafe(32)
        await db.auth_challenges.insert_one(
            {
                "challenge_id": challenge_id,
                "user_id": user["user_id"],
                "purpose": "login_2fa",
                "attempts": 0,
                "created_at": _now(),
                "expires_at": _now() + timedelta(minutes=5),
            }
        )
        return LoginResponse(
            status="two_factor_required",
            challenge_id=challenge_id,
            requires_2fa=True,
        )

    tokens = await _issue_session(db, user, response)
    await record_audit(
        "auth.login",
        user_id=user["user_id"],
        target_type="session",
    )
    return LoginResponse(
        status="authenticated",
        access_token=tokens.access_token,
    )


@router.post(
    "/2fa/verify-login",
    response_model=AuthResponse,
    dependencies=[rate_limit("auth.2fa", 10, 300)],
)
async def verify_login_2fa(
    payload: TwoFactorCodeRequest,
    response: Response,
):
    db = get_database()
    challenge = await db.auth_challenges.find_one_and_update(
        {
            "challenge_id": payload.challenge_id,
            "purpose": "login_2fa",
            "expires_at": {"$gt": _now()},
            "attempts": {"$lt": 5},
        },
        {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not challenge:
        raise HTTPException(400, "Invalid or expired two-factor challenge")

    user = await db.user.find_one({"user_id": challenge["user_id"]})
    if (
        not user
        or not user.get("two_factor_enabled")
        or not user.get("two_factor_secret")
    ):
        raise HTTPException(400, "Two-factor authentication is not configured")

    if not verify_totp(user["two_factor_secret"], payload.code):
        raise HTTPException(401, "Invalid two-factor code")

    await db.auth_challenges.delete_one({"_id": challenge["_id"]})
    tokens = await _issue_session(db, user, response)
    await record_audit(
        "auth.login_2fa",
        user_id=user["user_id"],
        target_type="session",
    )
    return tokens


@router.post("/2fa/setup", dependencies=[rate_limit("auth.2fa.setup", 5, 300)])
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


@router.post("/2fa/enable", dependencies=[rate_limit("auth.2fa.enable", 10, 300)])
async def enable_2fa(
    payload: TwoFactorVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    secret = current_user.get("two_factor_pending_secret")
    if not secret or not verify_totp(secret, payload.code):
        raise HTTPException(400, "Invalid verification code")
    await db.user.update_one(
        {"user_id": current_user["user_id"]},
        {
            "$set": {
                "two_factor_enabled": True,
                "two_factor_secret": secret,
                "updated_at": _now(),
            },
            "$unset": {"two_factor_pending_secret": ""},
        },
    )
    await record_audit(
        "auth.2fa_enabled",
        user_id=current_user["user_id"],
        target_type="user",
        target_id=current_user["user_id"],
    )
    return {"status": "enabled"}


@router.post("/2fa/disable", dependencies=[rate_limit("auth.2fa.disable", 10, 300)])
async def disable_2fa(
    payload: TwoFactorVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    secret = current_user.get("two_factor_secret")
    if (
        not current_user.get("two_factor_enabled")
        or not secret
        or not verify_totp(secret, payload.code)
    ):
        raise HTTPException(400, "Invalid verification code")
    db = get_database()
    await db.user.update_one(
        {"user_id": current_user["user_id"]},
        {
            "$set": {"two_factor_enabled": False, "updated_at": _now()},
            "$unset": {
                "two_factor_secret": "",
                "two_factor_pending_secret": "",
            },
        },
    )
    await record_audit(
        "auth.2fa_disabled",
        user_id=current_user["user_id"],
        target_type="user",
        target_id=current_user["user_id"],
    )
    return {"status": "disabled"}


@router.post(
    "/refresh",
    response_model=AuthResponse,
    dependencies=[rate_limit("auth.refresh", 30, 60)],
)
async def refresh(
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
    x_requested_with: str | None = Header(default=None),
):
    # The custom header makes browser refresh a non-simple CORS request and
    # blocks cross-site CSRF attempts against the cookie-based session rotation.
    if x_requested_with != "ShareM-Int-Xpo":
        raise HTTPException(403, "Refresh request rejected")

    token = (payload.refresh_token if payload else None) or refresh_cookie
    if not token:
        raise HTTPException(401, "Refresh session required")

    db = get_database()
    now = _now()
    # Rotate the refresh session atomically so concurrent refresh requests
    # cannot both redeem the same refresh token.
    session = await db.sessions.find_one_and_update(
        {
            "token_hash": hash_token(token),
            "revoked_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"revoked_at": now, "last_used_at": now}},
        return_document=ReturnDocument.BEFORE,
    )
    if not session:
        raise HTTPException(401, "Invalid or expired refresh session")

    user = await db.user.find_one({"user_id": session["user_id"]})
    if not user:
        raise HTTPException(401, "User session is invalid")

    return await _issue_session(db, user, response)


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
async def logout(
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    await db.sessions.update_many(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    _clear_refresh_cookie(response)
    await record_audit(
        "auth.logout",
        user_id=current_user["user_id"],
        target_type="user",
        target_id=current_user["user_id"],
    )
    return {"status": "logged_out"}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    result = await db.sessions.update_many(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    _clear_refresh_cookie(response)
    await record_audit(
        "auth.logout_all",
        user_id=current_user["user_id"],
        target_type="user",
        target_id=current_user["user_id"],
    )
    return {"status": "logged_out", "sessions_revoked": result.modified_count}
