from app.services.exchange_calendar import normalize_date, parse_holiday_csv


def test_holiday_parser():
    rows = parse_holiday_csv(
        b"exchange,date,description\nNSE,15-Aug-2026,Independence Day\n"
    )
    assert rows == [{
        "exchange": "NSE",
        "date": "2026-08-15",
        "description": "Independence Day",
    }]


def test_holiday_date_normalization():
    assert normalize_date("2026/08/15") == "2026-08-15"
