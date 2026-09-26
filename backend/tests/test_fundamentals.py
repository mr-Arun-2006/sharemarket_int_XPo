from app.services.fundamentals import parse_fundamentals_csv


def test_parse_fundamental_snapshot():
    csv_data = (
        "symbol,as_of,market_cap,eps,pe,pb,roe,roce,debt_to_equity,dividend_yield\n"
        "RELIANCE,2026-06-30,1900000,52.2,27.4,2.1,10.5,12.8,0.42,0.35\n"
    ).encode()
    rows = parse_fundamentals_csv(csv_data)
    assert rows[0]["symbol"] == "RELIANCE"
    assert rows[0]["as_of"] == "2026-06-30"
    assert rows[0]["pe"] == 27.4
    assert rows[0]["roe_pct"] == 10.5
