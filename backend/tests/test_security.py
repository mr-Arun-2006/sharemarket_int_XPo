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
        docs_enabled=False,
        auth_cookie_secure=True,
        auth_cookie_samesite="lax",
        smtp_host="smtp.example.com",
        smtp_user="user",
        smtp_password="password",
        smtp_from="ci@example.com",
    )
    with pytest.raises(ValueError, match="Wildcard ALLOWED_HOSTS"):
        cfg.validate_runtime()


def _valid_production_settings(**overrides):
    from app.core.config import Settings

    values = {
        "app_env": "production",
        "mongodb_uri": "mongodb://localhost:27017/test",
        "jwt_secret": "a" * 48,
        "cors_origins": "https://frontend.example.com",
        "allowed_hosts": "api.example.com",
        "docs_enabled": False,
        "auth_cookie_secure": True,
        "auth_cookie_samesite": "lax",
        "smtp_host": "smtp.example.com",
        "smtp_user": "user",
        "smtp_password": "password",
        "smtp_from": "ci@example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_config_rejects_enabled_api_docs():
    cfg = _valid_production_settings(docs_enabled=True)
    with pytest.raises(ValueError, match="DOCS_ENABLED must be false"):
        cfg.validate_runtime()


def test_production_config_rejects_placeholder_jwt_secret():
    cfg = _valid_production_settings(
        jwt_secret="replace-with-a-real-but-not-random-secret-12345"
    )
    with pytest.raises(ValueError, match="not a placeholder"):
        cfg.validate_runtime()


def test_production_config_requires_https_cors_origins():
    cfg = _valid_production_settings(cors_origins="http://frontend.example.com")
    with pytest.raises(ValueError, match="must use HTTPS"):
        cfg.validate_runtime()


def test_non_admin_cannot_grant_wildcard_or_admin_permissions():
    from fastapi import HTTPException
    from app.api.routes.admin import _assert_permissions_safe

    actor = {"role": "role_manager"}
    for permissions in (["*"], ["admin.users.manage"], ["admin.roles.manage"]):
        with pytest.raises(HTTPException) as error:
            _assert_permissions_safe(permissions, actor)
        assert error.value.status_code == 403


def test_non_admin_cannot_assign_privileged_roles():
    from fastapi import HTTPException
    from app.api.routes.admin import _assert_role_assignable

    actor = {"role": "user_manager"}
    for role in (
        {"name": "admin", "permissions": ["*"]},
        {"name": "supervisor", "permissions": ["admin.users.manage"]},
    ):
        with pytest.raises(HTTPException) as error:
            _assert_role_assignable(role, actor)
        assert error.value.status_code == 403


def test_admin_can_grant_privileged_permissions():
    from app.api.routes.admin import _assert_permissions_safe
    from app.api.routes.admin import _assert_role_assignable

    admin = {"role": "admin"}
    _assert_permissions_safe(["*"], admin)
    _assert_role_assignable({"name": "admin", "permissions": ["*"]}, admin)
