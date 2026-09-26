import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")

def _decode_secret(secret: str) -> bytes:
    padded = secret + "=" * (-len(secret) % 8)
    return base64.b32decode(padded, casefold=True)

def totp(secret: str, for_time: int | None = None, step: int = 30, digits: int = 6) -> str:
    counter = int((for_time if for_time is not None else time.time()) // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(_decode_secret(secret), msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)

def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not code.isdigit() or len(code) != 6:
        return False
    now = int(time.time())
    for delta in range(-window, window + 1):
        expected = totp(secret, now + delta * 30)
        if hmac.compare_digest(expected, code):
            return True
    return False

def build_otpauth_url(secret: str, account: str, issuer: str = "ShareM Int Xpo") -> str:
    label = urllib.parse.quote(f"{issuer}:{account}")
    params = urllib.parse.urlencode({
        "secret": secret,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    })
    return f"otpauth://totp/{label}?{params}"
