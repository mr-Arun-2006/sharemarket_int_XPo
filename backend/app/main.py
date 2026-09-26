from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongo import mongo_lifespan

app = FastAPI(title="ShareM Int Xpo API", version="1.0.0", lifespan=mongo_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "sharem-int-xpo-api", "database": settings.mongodb_database}

@app.get("/api/v1/health/mongo")
async def mongo_health():
    from app.db.mongo import get_mongo_client
    await get_mongo_client().admin.command("ping")
    return {"status": "ok", "mongodb": "reachable"}
