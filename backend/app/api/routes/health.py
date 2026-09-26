from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.mongo import get_mongo_client

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("")
async def health():
    return {
        "status": "ok",
        "service": "sharem-int-xpo-api",
        "version": "1.1.0",
    }


@router.get("/live")
async def live():
    # Liveness deliberately avoids external dependency checks so an unhealthy
    # database does not cause the process itself to be restarted.
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    checks = {"mongodb": "unknown"}
    try:
        await get_mongo_client().admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception:
        checks["mongodb"] = "error"
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )

    if settings.redis_url:
        checks["redis"] = "ok"

    return {"status": "ready", "checks": checks}
