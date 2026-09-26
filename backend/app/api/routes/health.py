from fastapi import APIRouter
from app.db.mongo import get_mongo_client

router = APIRouter(prefix="/api/v1/health", tags=["health"])

@router.get("/mongo")
async def mongo():
    await get_mongo_client().admin.command("ping")
    return {"status": "ok", "mongodb": "reachable"}
