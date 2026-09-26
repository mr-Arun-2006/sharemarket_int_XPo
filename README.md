# ShareM Int Xpo

Share Market Intelligence System focused on two distinct market experiences:

1. **Live Market** — simple live-price monitoring through WebSocket streaming.
2. **EOD Intelligence** — deep, evidence-backed analysis using the completed trading session and the previous five trading sessions.

## Product Architecture

```text
Next.js Frontend
      |
      v
FastAPI Backend
      |
      +--> MongoDB Atlas
      +--> Redis
      +--> NSE / BSE EOD ingestion
      +--> yfinance supplementary data
      +--> Live WebSocket provider
      +--> Free AI model gateway
```

### EOD Intelligence

NSE is the primary market universe with BSE comparison. The EOD engine combines market direction, indices, sectors, breadth, institutional activity, major movers/events, technical analysis, fundamentals, regime classification and evidence-backed AI explanation.

Deep stock analysis is generated only for stocks selected by the user.

### Live Market

Live prices are a monitoring layer rather than the deep-analysis layer. WebSocket streaming is used; when the live connection is unavailable, the system does not silently substitute polling.

## Backend

- Python / FastAPI
- Async PyMongo
- MongoDB Atlas
- Redis
- WebSocket
- Pydantic
- Configurable AI provider

## Repository Status

Backend implementation is being built incrementally with security, data lineage and testability as first-class concerns.

## Security

Secrets belong only in environment variables. No API key, database password or service credential should be committed to this repository.

## License

MIT


## Automated market-data pipeline

The backend includes a configurable IST scheduler. By default it runs on weekdays at **15:45 Asia/Kolkata**, after NSE's normal equity session close of 15:30. The scheduler is designed to ingest EOD equity data plus dedicated index data, store an SHA-256 source fingerprint, prevent duplicate ingestion, and record failures in `ingestion_runs`.

Configure these environment variables in `backend/.env`:

```env
DATA_SCHEDULER_ENABLED=true
INGESTION_TIMEOUT_SECONDS=45
NSE_EOD_URL_TEMPLATE=
BSE_EOD_URL_TEMPLATE=
NSE_INDEX_URL_TEMPLATE=
BSE_INDEX_URL_TEMPLATE=
```

URL templates may use `{date}`, `{ddmmyyyy}`, `{ddmmyy}`, or `{yyyymmdd}`. The source URL must be an official exchange/distribution endpoint available to the deployment.

NSE's current reports page lists **CM-UDiFF Common Bhavcopy Final (zip)** as the current capital-market bhavcopy and states that the older CM Bhavcopy/Common Bhavcopy CSV reports were discontinued from July 8, 2024. The repository therefore does not hard-code the discontinued CSV URL. citeturn116990search0turn623765view1

BSE states that its daily EOD bhav-copy and historical market-data products are available through its information-products offering; the production deployment should use the access method permitted for the account rather than assuming an unrestricted public endpoint. citeturn222845search3

The application market-status service uses the documented normal NSE equity session of **09:15-15:30 IST**. It intentionally does not claim holiday accuracy until an exchange holiday calendar is connected. citeturn485311search0

Admin controls:
```text
GET  /api/v1/admin/data-pipeline/status
POST /api/v1/admin/data-pipeline/run
```
