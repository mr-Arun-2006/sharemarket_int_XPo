import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    encoded = hash_password("StrongPassword123!")
    assert verify_password("StrongPassword123!", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_roundtrip():
    token = create_access_token("user-1", "user", "session-1")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["sid"] == "session-1"


def test_short_password_rejected():
    with pytest.raises(ValueError):
        hash_password("short")
