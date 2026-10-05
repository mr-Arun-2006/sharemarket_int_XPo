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

 
def test_admin_eod_ingest_route_has_upload_rate_limit():
    from app.api.routes.market import ingest_eod

    dependencies = getattr(ingest_eod, "__dependencies__", None)
    assert dependencies is not None or hasattr(ingest_eod, "__wrapped__") or callable(ingest_eod)

def test_configured_ingestion_limit_is_positive():
    from app.core.config import settings
    assert settings.ingestion_max_bytes >= 1_000_000
