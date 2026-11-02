from datetime import datetime, timedelta, timezone
import asyncio
import logging
import secrets

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from pymongo import ReturnDocument

from app.api.deps.auth import bearer, get_current_user
from app.api.deps.rate_limit import rate_limit
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_token
from app.core.totp import build_otpauth_url, generate_secret, verify_totp
from app.db.mongo import get_database
from app.schemas.auth import (
    AuthResponse,
    LoginResponse,
    RefreshRequest,
    TwoFactorCodeRequest,
    TwoFactorVerifyRequest,
)
from app.services.audit import record_audit
from app.services.firebase_auth import (
    FirebaseAccountLinkError,
    FirebaseAuthConfigurationError,
    sync_firebase_user,
    verify_firebase_id_token,
)

logger = logging.getLogger("sharem.auth")
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


async def _create_two_factor_challenge(db, user: dict) -> LoginResponse:
    challenge_id = secrets.token_urlsafe(32)
    now = _now()
    await db.auth_challenges.insert_one(
        {
            "challenge_id": challenge_id,
            "user_id": user["user_id"],
            "purpose": "login_2fa",
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=5),
        }
    )
    return LoginResponse(
        status="two_factor_required",
        challenge_id=challenge_id,
        requires_2fa=True,
    )


@router.post(
    "/firebase/exchange",
    response_model=LoginResponse,
    dependencies=[rate_limit("auth.firebase_exchange", 15, 60)],
)
async def firebase_exchange(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    """Exchange a verified Firebase ID token for the app's short-lived API session."""
    if credentials is None:
        raise HTTPException(401, "Firebase ID token is required")

    try:
        claims = await asyncio.to_thread(
            verify_firebase_id_token,
            credentials.credentials,
        )
    except FirebaseAuthConfigurationError as exc:
        logger.error("Firebase authentication is not configured: %s", exc)
        raise HTTPException(503, "Firebase authentication is not configured") from exc
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", type(exc).__name__)
        raise HTTPException(401, "Invalid or expired Firebase ID token") from exc

    if claims.get("email_verified") is not True:
        raise HTTPException(403, "Verify your email address before signing in")

    db = get_database()
    try:
        user = await sync_firebase_user(db, claims)
    except FirebaseAccountLinkError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(401, "Firebase identity is missing a verified email") from exc

    await record_audit(
        "auth.firebase_login",
        user_id=user["user_id"],
        target_type="session",
    )

    # Preserve the application's existing authenticator-app MFA for users who
    # had enabled it before Firebase became the identity provider.
    if user.get("two_factor_enabled"):
        return await _create_two_factor_challenge(db, user)

    tokens = await _issue_session(db, user, response)
    return LoginResponse(
        status="authenticated",
        access_token=tokens.access_token,
    )


@router.post("/register", status_code=status.HTTP_410_GONE)
async def legacy_register_disabled():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Registration is managed by Firebase Authentication. Use the frontend registration page.",
    )


@router.post("/login", status_code=status.HTTP_410_GONE)
async def legacy_login_disabled():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Login is managed by Firebase Authentication. Use the frontend login page.",
    )


@router.post("/verify", status_code=status.HTTP_410_GONE)
async def legacy_email_otp_disabled():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Email verification is managed by Firebase Authentication.",
    )


@router.post("/resend-verification", status_code=status.HTTP_410_GONE)
async def legacy_resend_email_otp_disabled():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Email verification emails are managed by Firebase Authentication.",
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
    # The custom header makes this a non-simple CORS request and blocks
    # cross-site CSRF attempts against cookie-based session rotation.
    if x_requested_with != "ShareM-Int-Xpo":
        raise HTTPException(403, "Refresh request rejected")

    token = (payload.refresh_token if payload else None) or refresh_cookie
    if not token:
        raise HTTPException(401, "Refresh session required")

    db = get_database()
    now = _now()
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
