from app.services.live_market import compute_live_relevance
from app.services.live_provider import LiveProvider


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
