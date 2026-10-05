from __future__ import annotations
import csv, io, re, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping
from app.schemas.market import EODRecord
from app.core.config import settings
from app.core.config import settings

class MarketDataParseError(ValueError): pass
def _clean_key(v:str)->str: return re.sub(r"[^a-z0-9]","",v.strip().lower())
def _float(v):
    if v is None: return None
    x=v.strip().replace(",","")
    if x in {"","-","NA","N/A","null","None"}: return None
    try: return float(x)
    except ValueError: return None
def _int(v):
    if v is None: return None
    try: return int(float(v.strip().replace(",","")))
    except (ValueError,AttributeError): return None
def _date(v):
    if not v: return None
    for fmt in ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%d-%b-%Y","%d%b%Y","%Y%m%d"):
        try: return datetime.strptime(v.strip(),fmt).date().isoformat()
        except ValueError: pass
    return None

@dataclass(frozen=True)
class ColumnAliases:
    symbol: tuple[str,...]; name: tuple[str,...]; trade_date: tuple[str,...]
    open: tuple[str,...]; high: tuple[str,...]; low: tuple[str,...]; close: tuple[str,...]
    previous_close: tuple[str,...]; volume: tuple[str,...]; turnover: tuple[str,...]; trades: tuple[str,...]

NSE_ALIASES=ColumnAliases(("symbol","tckrSymb","sym","securitysymbol"),("securityname","companyname","name","fininstrmNm"),("tradDt","tradeDate","tradedate","businessdate"),("opnPric","open","openprice"),("hghPric","high","highprice"),("lwPric","low","lowprice"),("clsPric","close","closeprice"),("prvsClsgPric","prevclose","previousclose"),("ttlTradgVol","totaltradedvolume","tottrdqty","volume"),("ttlTrfVal","totaltradevalue","turnover","netturnov","netturnover"),("ttlNbOfTxsExctd","totalnumberoftrades","nooftrades","trades"))
BSE_ALIASES=ColumnAliases(("sccode","scname","securitycode","symbol","scripcode","securityid"),("scname","securityname","scripname","name"),("tradedate","txn_date","date","businessdate"),("open","openprice","open_price"),("high","highprice","high_price"),("low","lowprice","low_price"),("close","closeprice","close_price"),("prevclose","previousclose","previous_close","pdcp"),("noofshrs","totalquantity","volume","tradedvolume"),("netturnov","netturnover","turnover","net_turnover"),("nooftrades","no_of_trades","trades"))

def _choose(row:Mapping[str,str],aliases:tuple[str,...]):
    normalized={_clean_key(k):v for k,v in row.items()}
    for alias in aliases:
        value=normalized.get(_clean_key(alias))
        if value not in (None,""): return value
    return None

def _read_csv(data:bytes):
    text=data.decode("utf-8-sig",errors="replace")
    try: dialect=csv.Sniffer().sniff(text[:4096],delimiters=",|;\t")
    except csv.Error: dialect=csv.excel
    reader=csv.DictReader(io.StringIO(text),dialect=dialect)
    if not reader.fieldnames: raise MarketDataParseError("CSV has no header row")
    return list(reader)

def parse_exchange_eod(data:bytes,exchange:str,filename:str="")->list[EODRecord]:
    source_file=filename or "eod.csv"
    if data[:2]==b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=[n for n in z.namelist() if n.lower().endswith((".csv",".txt"))]
            if not names: raise MarketDataParseError("ZIP contains no CSV/TXT data file")
            source_file=max(names,key=lambda n:z.getinfo(n).file_size)
            info = z.getinfo(source_file)
            if info.file_size > settings.ingestion_max_bytes:
                raise MarketDataParseError("ZIP entry exceeds INGESTION_MAX_BYTES")
            data=z.read(source_file)
            if len(data) > settings.ingestion_max_bytes:
                raise MarketDataParseError("Decompressed ZIP entry exceeds INGESTION_MAX_BYTES")
    aliases=NSE_ALIASES if exchange.upper()=="NSE" else BSE_ALIASES
    result=[]
    for row in _read_csv(data):
        symbol=_choose(row,aliases.symbol); trade_date=_date(_choose(row,aliases.trade_date))
        if not symbol or not trade_date: continue
        result.append(EODRecord(exchange=exchange.upper(),symbol=symbol.strip().upper(),trade_date=trade_date,name=_choose(row,aliases.name),open=_float(_choose(row,aliases.open)),high=_float(_choose(row,aliases.high)),low=_float(_choose(row,aliases.low)),close=_float(_choose(row,aliases.close)),previous_close=_float(_choose(row,aliases.previous_close)),volume=_float(_choose(row,aliases.volume)),turnover=_float(_choose(row,aliases.turnover)),trades=_int(_choose(row,aliases.trades)),source_file=source_file))
    return result

def build_ingestion_document(records:list[EODRecord],source:str,fetched_at:datetime|None=None)->dict:
    now=fetched_at or datetime.now(timezone.utc)
    dates=sorted({r.trade_date for r in records})
    missing=sum(1 for r in records if r.close is None or r.previous_close is None)
    return {"exchange":records[0].exchange if records else "NSE","trade_date":dates[-1] if dates else None,"source":source,"fetched_at":now,"records":[r.model_dump() for r in records],"records_seen":len(records),"records_missing_core_prices":missing,"status":"complete" if records and missing==0 else ("partial" if records else "failed")}
