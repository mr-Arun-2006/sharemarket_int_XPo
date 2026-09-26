import hashlib
import hmac
import secrets
import time
from base64 import urlsafe_b64encode, urlsafe_b64decode

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$8$1$" + urlsafe_b64encode(salt).decode() + "$" + urlsafe_b64encode(digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = urlsafe_b64decode(salt_b64.encode())
        expected = urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def create_opaque_token() -> str:
    return secrets.token_urlsafe(48)

def utc_ts() -> int:
    return int(time.time())
