import asyncio
from httpx import ASGITransport, AsyncClient

from app.api.routes.live import extract_websocket_access_token
from app.main import app


def test_websocket_token_extraction_requires_protocol_marker():
    token = "header.payload.signature"
    assert extract_websocket_access_token(f"sharem-auth,{token}") == token
    assert extract_websocket_access_token(token) is None
    assert extract_websocket_access_token(None) is None


def test_liveness_endpoint_is_dependency_free():
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://localhost",
        ) as client:
            return await client.get("/api/v1/health/live")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"

 
 
def test_oversized_eod_upload_is_rejected():
    import asyncio
    from fastapi import HTTPException
    from app.api.routes.market import _read_limited_upload
    from app.core.config import settings

    class FakeUpload:
        async def read(self, size=-1):
            return b"x" * (settings.ingestion_max_bytes + 1)

    async def run():
        try:
            await _read_limited_upload(FakeUpload())
        except HTTPException as exc:
            return exc.status_code
        return None

    assert asyncio.run(run()) == 413


def test_legacy_smtp_auth_routes_are_disabled():
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://localhost",
        ) as client:
            register = await client.post("/api/v1/auth/register")
            login = await client.post("/api/v1/auth/login")
            verify = await client.post("/api/v1/auth/verify")
            return register.status_code, login.status_code, verify.status_code

    assert asyncio.run(run()) == (410, 410, 410)
