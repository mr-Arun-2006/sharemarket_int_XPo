from app.services.market_data import parse_exchange_eod
from app.schemas.market import EODRecord


def test_parse_nse_udiff_aliases():
    csv_data = (
        "tckrSymb,fininstrmNm,tradDt,opnPric,hghPric,lwPric,clsPric,"
        "prvsClsgPric,ttlTradgVol,ttlTrfVal,ttlNbOfTxsExctd\n"
        "RELIANCE,Reliance Industries,25-Sep-2026,1400,1420,1390,1410,1395,100000,141000000,5000\n"
    ).encode()
    rows = parse_exchange_eod(csv_data, "NSE")
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, EODRecord)
    assert row.symbol == "RELIANCE"
    assert row.trade_date == "2026-09-25"
    assert row.close == 1410
    assert row.previous_close == 1395
    assert row.volume == 100000
