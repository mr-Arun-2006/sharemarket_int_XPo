import struct

from app.services.live_market import compute_live_relevance
from app.services.live_provider import LiveProvider, decode_upstox_v3_message


def _varint(value: int) -> bytes:
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _length_delimited(field_number: int, payload: bytes) -> bytes:
    return _varint((field_number << 3) | 2) + _varint(len(payload)) + payload


def _double(field_number: int, value: float) -> bytes:
    return _varint((field_number << 3) | 1) + struct.pack("<d", value)


def _integer(field_number: int, value: int) -> bytes:
    return _varint(field_number << 3) + _varint(value)


def test_live_relevance_is_bounded():
    score = compute_live_relevance({
        "change_pct": 12.0,
        "volume": 10_000_000,
        "unusual_activity": 2.0,
        "event_flag": True,
    })
    assert 0.0 <= score <= 100.0


def test_live_provider_normalizes_tick():
    tick = LiveProvider._normalize_tick({
        "data": {
            "exchange": "nse",
            "symbol": "reliance",
            "price": "1410.25",
            "previous_close": "1395",
            "change_pct": "1.09",
            "volume": "100000",
        }
    })
    assert tick["exchange"] == "NSE"
    assert tick["symbol"] == "RELIANCE"
    assert tick["price"] == 1410.25


def test_live_provider_rejects_non_tick():
    assert LiveProvider._normalize_tick({"data": {"symbol": "RELIANCE"}}) is None


def test_upstox_v3_protobuf_decodes_index_ltp_and_change():
    ltpc = (
        _double(1, 22500.5)
        + _integer(2, 1760000000000)
        + _integer(3, 10)
        + _double(4, 22400.0)
    )
    feed = _length_delimited(1, ltpc)
    map_entry = (
        _length_delimited(1, b"NSE_INDEX|Nifty 50")
        + _length_delimited(2, feed)
    )
    message = _length_delimited(2, map_entry)

    ticks = decode_upstox_v3_message(message)

    assert len(ticks) == 1
    assert ticks[0]["exchange"] == "NSE"
    assert ticks[0]["symbol"] == "NIFTY 50"
    assert ticks[0]["price"] == 22500.5
    assert ticks[0]["previous_close"] == 22400.0
    assert ticks[0]["volume"] is None
    assert round(ticks[0]["change_pct"], 4) == round((100.5 / 22400) * 100, 4)


def test_upstox_v3_protobuf_uses_symbol_map_for_equities():
    ltpc = _double(1, 1410.25) + _double(4, 1395.0)
    feed = _length_delimited(1, ltpc)
    key = "NSE_EQ|INE002A01018"
    map_entry = _length_delimited(1, key.encode()) + _length_delimited(2, feed)
    message = _length_delimited(2, map_entry)

    ticks = decode_upstox_v3_message(
        message,
        {key: {"exchange": "NSE", "symbol": "RELIANCE"}},
    )

    assert len(ticks) == 1
    assert ticks[0]["symbol"] == "RELIANCE"
    assert ticks[0]["price"] == 1410.25
    assert ticks[0]["previous_close"] == 1395.0
