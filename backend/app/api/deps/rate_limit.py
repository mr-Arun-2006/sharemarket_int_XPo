from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable
import ipaddress

from fastapi import Depends, HTTPException, Request
from pymongo import ReturnDocument

from app.core.config import settings
from app.db.mongo import get_database


def rate_limit(scope: str, limit: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        now = datetime.now(timezone.utc)
        window_start_epoch = int(now.timestamp() // window_seconds) * window_seconds
        if settings.trust_proxy_headers:
            candidate = (
                request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
                or request.headers.get("x-real-ip", "").strip()
            )
            try:
                client_id = str(ipaddress.ip_address(candidate))
            except ValueError:
                client_id = request.client.host if request.client else "unknown"
        else:
            client_id = request.client.host if request.client else "unknown"
        key = f"{scope}:{client_id}:{window_start_epoch}"
        expires_at = now + timedelta(seconds=window_seconds + 60)
        row = await get_database().rate_limits.find_one_and_update(
            {"key": key},
            {
                "$setOnInsert": {
                    "key": key,
                    "scope": scope,
                    "created_at": now,
                    "expires_at": expires_at,
                },
                "$inc": {"count": 1},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0, "count": 1},
        )
        count = int((row or {}).get("count", 0))
        if count > limit:
            retry_after = max(
                1,
                int((window_start_epoch + window_seconds) - now.timestamp()) + 1,
            )
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return Depends(dependency)
