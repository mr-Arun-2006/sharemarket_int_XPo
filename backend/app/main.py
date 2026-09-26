from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongo import mongo_lifespan
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.intelligence import router as intelligence_router

app = FastAPI(title="ShareM Int Xpo API", version="1.0.0", lifespan=mongo_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "sharem-int-xpo-api"}

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(market_router)
app.include_router(intelligence_router)
