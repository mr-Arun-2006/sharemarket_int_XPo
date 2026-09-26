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
        "environment": settings.app_env,
    }


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    checks = {"mongodb": "unknown"}
    try:
        await get_mongo_client().admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = "error"
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks, "error": str(exc)[:500]},
        )

    return {"status": "ready", "checks": checks}
