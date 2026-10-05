import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.db.mongo import mongo_lifespan
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.live import router as live_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.admin import router as admin_router
from app.api.routes.stocks import router as stocks_router
from app.api.routes.screener import router as screener_router
from app.api.routes.exchanges import router as exchanges_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.reports import router as reports_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.context import router as context_router
from app.api.routes.fundamentals import router as fundamentals_router
from app.api.routes.strategies import router as strategies_router

logger = logging.getLogger("sharem.api")

app = FastAPI(
    title="ShareM Int Xpo API",
    version="1.2.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=mongo_lifespan,
)


def _request_id(value: str | None) -> str:
    if value and len(value) <= 64 and all(ch.isalnum() or ch in "-_" for ch in value):
        return value
    return uuid4().hex


app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_host_list,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = _request_id(request.headers.get("x-request-id"))
    request.state.request_id = request_id
    started = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.exception(
        json.dumps(
            {
                "event": "unhandled_exception",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
            }
        )
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


app.include_router(auth_router)
app.include_router(health_router)
app.include_router(market_router)
app.include_router(intelligence_router)
app.include_router(live_router)
app.include_router(sessions_router)
app.include_router(admin_router)
app.include_router(stocks_router)
app.include_router(screener_router)
app.include_router(exchanges_router)
app.include_router(alerts_router)
app.include_router(reports_router)
app.include_router(portfolio_router)
app.include_router(context_router)
app.include_router(fundamentals_router)
app.include_router(strategies_router)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.app_env.lower() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
