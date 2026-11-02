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

NSE's current reports page lists **CM-UDiFF Common Bhavcopy Final (zip)** as the current capital-market bhavcopy and states that the older CM Bhavcopy/Common Bhavcopy CSV reports were discontinued from July 8, 2024. The repository therefore does not hard-code the discontinued CSV URL.

BSE states that its daily EOD bhav-copy and historical market-data products are available through its information-products offering; the production deployment should use the access method permitted for the account rather than assuming an unrestricted public endpoint.

The application market-status service uses the normal NSE equity session of **09:15-15:30 IST** and can use the stored exchange-holiday calendar when it is populated.

Admin controls:
```text
GET  /api/v1/admin/data-pipeline/status
POST /api/v1/admin/data-pipeline/run
```



## Official NSE report download

The production NSE cash-market EOD path uses the same current report exposed by the official NSE All Reports portal: **CM-UDiFF Common Bhavcopy Final (zip)**. The backend opens the official All Reports page, creates the required NSE web session, calls the report service for the selected date, downloads the ZIP response, validates the embedded trade date, fingerprints the payload with SHA-256, and stores the normalized rows in MongoDB. NSE's current All Reports page lists this report and marks the older CM CSV bhavcopy reports discontinued from July 8, 2024.

The UDiFF file specification and sample/test files are published by NSE in its Forms & Formats section.

The NSE institutional pipeline uses the official FII/FPI & DII report service and stores Buy Value, Sell Value and Net Value for the exact trading date associated with the downloaded EOD session.

BSE EOD remains configuration-driven because its permitted distribution/access model differs from the public NSE report flow.

Environment variables:

    DATA_SCHEDULER_ENABLED=true
    INGESTION_TIMEOUT_SECONDS=45
    NSE_EOD_URL_TEMPLATE=
    BSE_EOD_URL_TEMPLATE=
    NSE_INDEX_URL_TEMPLATE=
    BSE_INDEX_URL_TEMPLATE=
    NSE_INSTITUTIONAL_URL_TEMPLATE=
    NSE_EVENTS_URL_TEMPLATE=
    SECTOR_MAPPING_URL_TEMPLATE=

NSE_EOD_URL_TEMPLATE is intentionally empty: NSE uses the built-in official All Reports downloader. It may still be used as an explicit override for testing or a controlled deployment.

Admin controls:

    GET  /api/v1/admin/data-pipeline/status
    POST /api/v1/admin/data-pipeline/run

## Quality and production hardening

The repository CI validates backend tests, Python compilation, frontend TypeScript and the Next.js production build.

Backend hardening includes authentication rate limiting, trusted-host validation, security response headers, distributed scheduler locking, Redis live-market pub/sub, configurable live-provider reconnect handling, source-backed fundamental data, exchange holiday support, and explicit data-status handling.

Frontend hardening includes a shared API client with one-shot access-token refresh, network error handling, a global loading state, a global error boundary, reconnecting WebSocket market monitoring, dedicated index-data rendering, responsive/accessibility states, and TypeScript/build validation.

Provider credentials are intentionally external configuration. Deployment is not executed by the repository CI.
### Authentication hardening

Firebase Authentication is the identity provider for frontend registration, email/password login, and email verification. The backend verifies Firebase ID tokens with the Firebase Admin SDK, then creates the application's own short-lived API token and HttpOnly refresh-cookie session. MongoDB remains the application profile and authorization database; existing roles, AI preferences, and authenticator-app MFA are preserved when an existing MongoDB profile is linked by its verified email.

The frontend uses Firebase Authentication's HTTPS REST API. Enable **Email/Password** in Firebase Authentication > Sign-in method, configure the email verification template, and add the frontend Vercel domain under Authentication > Settings > Authorized domains.

Frontend environment:
- `NEXT_PUBLIC_FIREBASE_API_KEY` — Firebase web API key (public browser configuration).
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID` — Firebase project ID.
- `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_WS_BASE_URL` — the backend's HTTPS and WSS origins.

Backend secrets:
- `FIREBASE_PROJECT_ID` — must match the service account project.
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` — base64-encoded Firebase service-account JSON. Keep it in Vercel backend environment variables only; never commit the JSON or its private key.

To encode the downloaded service-account JSON locally on PowerShell:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes(".\firebase-service-account.json"))
```

The old custom email-OTP registration/login API routes return HTTP 410 and no longer send SMTP messages. SMTP credentials are not required for Firebase email verification. The app still uses its own backend refresh cookie to preserve the existing MongoDB session revocation and role-permission checks.

Access tokens are kept only in browser memory. Refresh tokens are never persisted in JavaScript storage; the backend issues them as HttpOnly cookies. Production deployments should set:

    APP_ENV=production
    AUTH_COOKIE_SECURE=true
    AUTH_COOKIE_SAMESITE=none
    CORS_ORIGINS=https://<your-frontend-domain>
    ALLOWED_HOSTS=<your-api-domain>

The refresh endpoint requires the `X-Requested-With: ShareM-Int-Xpo` header to add a CSRF barrier for browser session rotation.

### Live WebSocket security

The market WebSocket requires an authenticated short-lived access token supplied through the WebSocket subprotocol handshake rather than the URL. Connections are capped by `LIVE_MAX_CONNECTIONS` and receive periodic heartbeat frames controlled by `LIVE_HEARTBEAT_SECONDS`.

### Operational safety

Remote market-data downloads enforce `INGESTION_TIMEOUT_SECONDS` and `INGESTION_MAX_BYTES`. The EOD scheduler uses a distributed MongoDB lease that renews during long-running ingestion so multiple backend instances do not start the same job concurrently.

Production logs include a request ID that is returned in the `X-Request-ID` response header, allowing an operational log entry and a user-visible error to be correlated without exposing exception internals.

## Security audit

See [Production Readiness & Security Audit](docs/PRODUCTION_SECURITY_AUDIT.md) for reviewed controls, findings, and the release checklist. This is a static review, not a penetration test or production certification.

## Production deployment

Before deployment, set the backend environment to production and provide only deployment-managed secrets.

APP_ENV=production
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
DOCS_ENABLED=false
CORS_ORIGINS=https://<frontend-domain>
ALLOWED_HOSTS=<api-domain>
TRUST_PROXY_HEADERS=true
MONGODB_URI=<managed-mongodb-uri>
JWT_SECRET=<long-random-secret>
REDIS_URL=<managed-redis-url>
AI_BASE_URL=<provider-base-or-chat-completions-url>
AI_API_KEY=<provider-secret>
AI_MODEL=<provider-model>

Expose /api/v1/health/live for liveness and /api/v1/health/ready for readiness, with HTTPS at the public edge.

This branch adds database indexes and TTLs, bounded ingestion uploads, bounded AI context, heavy-endpoint rate limits, dependency validation, application import validation, frontend security headers, and regression coverage for stock intelligence.

BSE EOD and optional index/context feeds remain deployment configuration because permitted source access varies by provider.


## Live market provider: Upstox V3

The live dashboard supports an optional Upstox Market Data Feed V3 adapter. It connects through the Upstox authorization endpoint, subscribes to configured instrument keys, decodes the binary Protobuf feed, and passes normalized ticks into the existing live market pipeline. The EOD ingestion and AI diagnosis paths do not depend on this provider.

Configure these backend environment variables:

| Variable | Purpose |
| --- | --- |
| `LIVE_PROVIDER_TYPE` | Set to `upstox_v3` to enable the Upstox adapter; defaults to `generic`. |
| `UPSTOX_ACCESS_TOKEN` | User-specific Upstox OAuth access token. Store as a deployment secret. |
| `UPSTOX_INSTRUMENT_KEYS` | Comma-separated instrument keys to subscribe to, such as index or equity keys from the Upstox instrument master. |
| `UPSTOX_SYMBOL_MAP_JSON` | Optional JSON object that maps equity instrument keys to readable symbols and exchange names. |
| `UPSTOX_MODE` | `ltpc` for price/previous-close ticks, or `full` / `full_d30` where supported by the account and feed limits. |

Example symbol map (replace the instrument key with the current key from the Upstox instrument master):

```json
{
  "NSE_EQ|INE002A01018": {
    "exchange": "NSE",
    "symbol": "RELIANCE"
  }
}
```

Upstox instrument keys can change with instrument-master updates. Resolve and validate keys against the current instrument master instead of hardcoding them into the application. The adapter's default `ltpc` mode is intended for a watchlist/dashboard, not full market depth. A valid access token and configured instrument keys are required before the provider worker starts.

Official references:
- [Upstox Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
- [Upstox Market Data Feed Authorize V3](https://upstox.com/developer/api-documentation/get-market-data-feed-authorize-v3/)

The live feed is a separate broker-authenticated source. It is not treated as a substitute for official NSE/BSE EOD files, and the app should be deployed for personal/internal use only unless the provider's data terms permit the intended distribution.


## Firebase Authentication migration
New Firebase registrations create MongoDB application profiles on the first successful, email-verified Firebase token exchange. Existing profiles are linked by their normalized, verified email address; their existing `user_id`, role, AI language, and TOTP MFA settings are retained. A profile already linked to a different Firebase UID is rejected rather than reassigned. The backend enforces a unique sparse index on `firebase_uid`.

Firebase REST API and Admin SDK references:
- https://firebase.google.com/docs/reference/rest/auth
- https://firebase.google.com/docs/auth/admin/verify-id-tokens
- https://firebase.google.com/docs/admin/setup
