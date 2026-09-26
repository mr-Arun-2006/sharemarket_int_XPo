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
