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


def test_access_token_rejects_payload_tampering():
    token = create_access_token("user-1", "user", "session-1")
    header, payload, signature = token.split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join((header, tampered_payload, signature))
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_access_token_rejects_signature_tampering():
    token = create_access_token("user-1", "user", "session-1")
    header, payload, signature = token.split(".")
    tampered_signature = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    tampered = ".".join((header, payload, tampered_signature))
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_refresh_cookie_security_flags(monkeypatch):
    from fastapi import Response
    from app.api.routes.auth import _set_refresh_cookie
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_samesite", "none")
    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    response = Response()
    _set_refresh_cookie(response, "test-refresh-token")
    cookie = response.headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=none" in cookie
    assert "path=/api/v1/auth" in cookie


def test_production_config_rejects_wildcard_hosts():
    from app.core.config import Settings

    cfg = Settings(
        app_env="production",
        mongodb_uri="mongodb://localhost:27017/test",
        jwt_secret="x" * 48,
        cors_origins="https://frontend.example.com",
        allowed_hosts="*",
        auth_cookie_secure=True,
        auth_cookie_samesite="lax",
        smtp_host="smtp.example.com",
        smtp_user="user",
        smtp_password="password",
        smtp_from="ci@example.com",
    )
    with pytest.raises(ValueError, match="Wildcard ALLOWED_HOSTS"):
        cfg.validate_runtime()
