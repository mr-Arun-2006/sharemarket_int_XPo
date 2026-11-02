from __future__ import annotations

import asyncio
import json
import logging
import struct
from typing import Any, Awaitable, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

UPSTOX_AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise ValueError("Malformed protobuf varint")


def _iter_protobuf_fields(data: bytes):
    """Yield (field_number, wire_type, value) for the protobuf wire types used by Upstox."""
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        field_number, wire_type = tag >> 3, tag & 0x07
        if field_number == 0:
            raise ValueError("Invalid protobuf field number")

        if wire_type == 0:
            value, offset = _read_varint(data, offset)
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise ValueError("Truncated protobuf fixed64 field")
            value = data[offset:end]
            offset = end
        elif wire_type == 2:
            length, offset = _read_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise ValueError("Truncated protobuf length-delimited field")
            value = data[offset:end]
            offset = end
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise ValueError("Truncated protobuf fixed32 field")
            value = data[offset:end]
            offset = end
        else:
            raise ValueError(f"Unsupported protobuf wire type: {wire_type}")

        yield field_number, wire_type, value


def _parse_ltpc(payload: bytes) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {
        "price": None,
        "previous_close": None,
        "last_trade_time": None,
        "last_trade_quantity": None,
    }
    for number, wire_type, value in _iter_protobuf_fields(payload):
        if number == 1 and wire_type == 1:
            values["price"] = struct.unpack("<d", value)[0]
        elif number == 2 and wire_type == 0:
            values["last_trade_time"] = int(value)
        elif number == 3 and wire_type == 0:
            values["last_trade_quantity"] = int(value)
        elif number == 4 and wire_type == 1:
            values["previous_close"] = struct.unpack("<d", value)[0]
    return values


def _extract_upstox_ltpc(feed_payload: bytes) -> tuple[dict[str, Any] | None, float | None]:
    """Extract LTPC fields from an Upstox Feed, including direct, full and first-level modes."""
    volume_traded: float | None = None

    for number, wire_type, value in _iter_protobuf_fields(feed_payload):
        if wire_type != 2:
            continue

        if number == 1:
            return _parse_ltpc(value), volume_traded

        if number == 3:
            for nested_number, nested_wire, nested_value in _iter_protobuf_fields(value):
                if nested_number == 1 and nested_wire == 2:
                    return _parse_ltpc(nested_value), volume_traded

        if number == 2:
            # FullFeed contains either MarketFullFeed (field 1) or IndexFullFeed (field 2).
            for full_number, full_wire, full_value in _iter_protobuf_fields(value):
                if full_wire != 2 or full_number not in (1, 2):
                    continue
                for item_number, item_wire, item_value in _iter_protobuf_fields(full_value):
                    if item_number == 1 and item_wire == 2:
                        ltpc = _parse_ltpc(item_value)
                    elif item_number == 6 and item_wire == 0:
                        # MarketFullFeed.vtt is total traded volume; index feeds omit it.
                        volume_traded = float(item_value)
                if "ltpc" in locals():
                    return ltpc, volume_traded

    return None, volume_traded


def decode_upstox_v3_message(
    payload: bytes,
    symbol_map: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Decode only the Upstox V3 fields required by the live price dashboard."""
    symbol_map = symbol_map or {}
    ticks: list[dict[str, Any]] = []

    for number, wire_type, entry_payload in _iter_protobuf_fields(payload):
        if number != 2 or wire_type != 2:
            continue

        instrument_key = ""
        feed_payload: bytes | None = None
        for entry_number, entry_wire, entry_value in _iter_protobuf_fields(entry_payload):
            if entry_number == 1 and entry_wire == 2:
                instrument_key = entry_value.decode("utf-8", errors="replace")
            elif entry_number == 2 and entry_wire == 2:
                feed_payload = entry_value

        if not instrument_key or feed_payload is None:
            continue

        ltpc, volume = _extract_upstox_ltpc(feed_payload)
        if not ltpc or ltpc.get("price") is None:
            continue

        mapped = symbol_map.get(instrument_key)
        if isinstance(mapped, str):
            symbol = mapped
            exchange = instrument_key.split("_", 1)[0].upper()
        elif isinstance(mapped, dict):
            symbol = str(mapped.get("symbol") or "").strip()
            exchange = str(mapped.get("exchange") or instrument_key.split("_", 1)[0]).upper()
        else:
            segment, _, instrument = instrument_key.partition("|")
            exchange = segment.split("_", 1)[0].upper()
            symbol = instrument if segment.endswith("_INDEX") else instrument

        if exchange not in {"NSE", "BSE"} or not symbol:
            continue

        price = float(ltpc["price"])
        previous_close = ltpc.get("previous_close")
        previous_close = float(previous_close) if previous_close is not None else None
        change_pct = (
            (price - previous_close) / previous_close * 100
            if previous_close not in (None, 0)
            else None
        )

        ticks.append(
            {
                "exchange": exchange,
                "symbol": symbol.upper(),
                "name": symbol,
                "price": price,
                "previous_close": previous_close,
                "change_pct": change_pct,
                "volume": volume,
            }
        )

    return ticks


class LiveProvider:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.running = False
        self.connected = False

    async def start(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if self.running:
            return

        provider_type = settings.live_provider_type.strip().lower()
        if provider_type == "upstox_v3":
            if not settings.upstox_access_token or not settings.upstox_instrument_keys.strip():
                logger.warning("Upstox V3 selected but access token or instrument keys are missing")
                return
            try:
                symbol_map = json.loads(settings.upstox_symbol_map_json or "{}")
                if not isinstance(symbol_map, dict):
                    raise ValueError("UPSTOX_SYMBOL_MAP_JSON must be a JSON object")
            except ValueError:
                logger.exception("Invalid UPSTOX_SYMBOL_MAP_JSON")
                return
            self.running = True
            self.task = asyncio.create_task(self._run_upstox_v3(handler, symbol_map))
            return

        if provider_type != "generic":
            logger.error("Unsupported LIVE_PROVIDER_TYPE: %s", provider_type)
            return
        if not settings.live_provider_url:
            return

        self.running = True
        self.task = asyncio.create_task(self._run_generic(handler))

    async def stop(self) -> None:
        self.running = False
        self.connected = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _run_generic(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        import websockets

        delay = 2.0
        while self.running:
            try:
                extra_headers = {}
                if settings.live_provider_api_key:
                    extra_headers["Authorization"] = "Bearer " + settings.live_provider_api_key
                async with websockets.connect(
                    settings.live_provider_url,
                    additional_headers=extra_headers,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2 * 1024 * 1024,
                ) as connection:
                    self.connected = True
                    delay = 2.0
                    subscribe = settings.live_provider_subscribe_json
                    if subscribe:
                        await connection.send(subscribe)
                    async for raw in connection:
                        try:
                            message = json.loads(raw)
                            tick = self._normalize_tick(message)
                            if tick:
                                await handler(tick)
                        except Exception:
                            logger.exception("Live provider message normalization failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Live market provider connection failed")
                await asyncio.sleep(delay)
                delay = min(delay * 2.0, 30.0)
            finally:
                self.connected = False

    async def _run_upstox_v3(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        symbol_map: dict[str, Any],
    ) -> None:
        import httpx
        import websockets

        instrument_keys = [
            value.strip()
            for value in settings.upstox_instrument_keys.split(",")
            if value.strip()
        ]
        if not instrument_keys:
            logger.error("UPSTOX_INSTRUMENT_KEYS contains no instrument keys")
            self.running = False
            return

        delay = 2.0
        while self.running:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(
                        UPSTOX_AUTHORIZE_URL,
                        headers={
                            "Authorization": "Bearer " + settings.upstox_access_token,
                            "Accept": "application/json",
                        },
                    )
                    response.raise_for_status()
                    response_data = response.json()
                    socket_url = (
                        response_data.get("data", {}).get("authorized_redirect_uri")
                        if isinstance(response_data, dict)
                        else None
                    )
                    if not socket_url:
                        raise ValueError("Upstox authorization response has no WebSocket URL")

                subscription = {
                    "guid": "sharem-int-xpo",
                    "method": "sub",
                    "data": {
                        "mode": settings.upstox_mode,
                        "instrumentKeys": instrument_keys,
                    },
                }

                async with websockets.connect(
                    socket_url,
                    additional_headers={"Accept": "*/*"},
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2 * 1024 * 1024,
                ) as connection:
                    self.connected = True
                    delay = 2.0
                    # Upstox V3 expects the JSON subscription as a binary WebSocket frame.
                    await connection.send(json.dumps(subscription).encode("utf-8"))
                    async for raw in connection:
                        if not isinstance(raw, bytes):
                            continue
                        try:
                            ticks = decode_upstox_v3_message(raw, symbol_map)
                            for tick in ticks:
                                await handler(tick)
                        except Exception:
                            logger.exception("Unable to decode Upstox V3 market message")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Upstox V3 market connection failed")
                await asyncio.sleep(delay)
                delay = min(delay * 2.0, 60.0)
            finally:
                self.connected = False

    @staticmethod
    def _normalize_tick(message: Any) -> dict[str, Any] | None:
        data = message.get("data", message) if isinstance(message, dict) else None
        if not isinstance(data, dict):
            return None
        exchange = data.get("exchange")
        symbol = data.get("symbol")
        price = data.get("price")
        if not exchange or not symbol or price in (None, ""):
            return None
        return {
            "exchange": str(exchange).upper(),
            "symbol": str(symbol).upper(),
            "name": data.get("name"),
            "price": float(price),
            "previous_close": float(data["previous_close"]) if data.get("previous_close") not in (None, "") else None,
            "change_pct": float(data["change_pct"]) if data.get("change_pct") not in (None, "") else None,
            "volume": float(data["volume"]) if data.get("volume") not in (None, "") else None,
            "unusual_activity": float(data.get("unusual_activity") or 0.0),
            "event_flag": bool(data.get("event_flag")),
        }

    @staticmethod
    def _decode_upstox_message(
        payload: bytes,
        symbol_map: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return decode_upstox_v3_message(payload, symbol_map)


live_provider = LiveProvider()
