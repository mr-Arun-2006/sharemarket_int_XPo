import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings

def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$8$1$" + _b64(salt) + "$" + _b64(digest)

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt_b64), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, _unb64(digest_b64))
    except (ValueError, TypeError):
        return False

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def create_access_token(user_id: str, role: str, session_id: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "role": role,
        "sid": session_id,
        "iat": now,
        "exp": now + settings.access_token_minutes * 60,
    }
    signing_input = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64(signature)

def decode_access_token(token: str) -> dict:
    header_b64, payload_b64, signature_b64 = token.split(".")
    signing_input = header_b64 + "." + payload_b64
    expected = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _unb64(signature_b64)):
        raise ValueError("Invalid token signature")
    header = json.loads(_unb64(header_b64))
    payload = json.loads(_unb64(payload_b64))
    if header.get("alg") != "HS256" or payload.get("exp", 0) <= int(time.time()):
        raise ValueError("Expired or invalid token")
    return payload
