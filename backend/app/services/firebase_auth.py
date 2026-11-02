from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any
from threading import Lock

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import settings


_firebase_app = None
_firebase_init_lock = Lock()


class FirebaseAuthConfigurationError(RuntimeError):
    """Raised when Firebase Admin credentials are not configured correctly."""


class FirebaseAccountLinkError(RuntimeError):
    """Raised when an existing application account is linked to another Firebase UID."""


def _initialize_firebase_app():
    global _firebase_app
    project_id = settings.firebase_project_id.strip()
    encoded_credentials = settings.firebase_service_account_json_base64.strip()
    if not project_id or not encoded_credentials:
        raise FirebaseAuthConfigurationError(
            "Firebase Admin credentials are not configured on the backend"
        )

    with _firebase_init_lock:
        if _firebase_app is not None:
            if _firebase_app.project_id != project_id:
                raise FirebaseAuthConfigurationError(
                    "An initialized Firebase Admin app uses a different project"
                )
            return _firebase_app

        try:
            service_account_info = json.loads(
                base64.b64decode(encoded_credentials, validate=True).decode("utf-8")
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FirebaseAuthConfigurationError(
                "FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 is not valid base64-encoded JSON"
            ) from exc

        if service_account_info.get("project_id") != project_id:
            raise FirebaseAuthConfigurationError(
                "FIREBASE_PROJECT_ID does not match the Firebase service account project"
            )

        try:
            try:
                app = firebase_admin.get_app()
            except ValueError:
                credential = credentials.Certificate(service_account_info)
                app = firebase_admin.initialize_app(
                    credential,
                    options={"projectId": project_id},
                )
        except Exception as exc:
            raise FirebaseAuthConfigurationError(
                "Firebase Admin could not initialize; check the service account credentials"
            ) from exc

        if app.project_id != project_id:
            raise FirebaseAuthConfigurationError(
                "An initialized Firebase Admin app uses a different project"
            )
        _firebase_app = app
        return app

def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience, expiry, and revocation with Firebase Admin."""
    if not id_token or len(id_token) > 8192:
        raise ValueError("Invalid Firebase ID token")
    app = _initialize_firebase_app()
    return auth.verify_id_token(id_token, app=app, check_revoked=True)


async def sync_firebase_user(db, claims: dict[str, Any]) -> dict[str, Any]:
    """Create or safely link a verified Firebase identity to its MongoDB profile.

    Existing application roles and preferences are preserved. A verified Firebase
    email can claim an older MongoDB profile; an already-linked different UID cannot.
    """
    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    if not uid or not email or claims.get("email_verified") is not True:
        raise ValueError("Firebase token must contain a UID and a verified email")

    now = datetime.now(timezone.utc)
    users = db.user
    user = await users.find_one({"firebase_uid": uid})
    if user is None:
        user = await users.find_one({"email_normalized": email})

    if user is not None:
        linked_uid = user.get("firebase_uid")
        if linked_uid and linked_uid != uid:
            raise FirebaseAccountLinkError(
                "This application account is already linked to another Firebase identity"
            )
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "firebase_uid": uid,
                    "email": email,
                    "email_normalized": email,
                    "email_verified": True,
                    "updated_at": now,
                }
            },
        )
        updated = await users.find_one({"_id": user["_id"]})
        if not updated:
            raise RuntimeError("Unable to load the linked application user")
        return updated

    new_user = {
        "user_id": uid,
        "firebase_uid": uid,
        "email": email,
        "email_normalized": email,
        "display_name": str(claims.get("name") or "").strip(),
        "role": "user",
        "ai_language": "en",
        "email_verified": True,
        "two_factor_enabled": False,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await users.insert_one(new_user)
    except Exception as exc:
        # A concurrent registration may have inserted the same Firebase UID or
        # email. Re-read only these unique identities; do not silently merge
        # unrelated accounts.
        user = await users.find_one({"firebase_uid": uid})
        if user is None:
            user = await users.find_one({"email_normalized": email})
        if user is None:
            raise
        linked_uid = user.get("firebase_uid")
        if linked_uid and linked_uid != uid:
            raise FirebaseAccountLinkError(
                "This application account is already linked to another Firebase identity"
            ) from exc
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "firebase_uid": uid,
                    "email": email,
                    "email_normalized": email,
                    "email_verified": True,
                    "updated_at": now,
                }
            },
        )
        updated = await users.find_one({"_id": user["_id"]})
        if not updated:
            raise RuntimeError("Unable to load the linked application user") from exc
        return updated

    created = await users.find_one({"firebase_uid": uid})
    if not created:
        raise RuntimeError("Unable to load the created application user")
    return created
