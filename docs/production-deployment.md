# Production Deployment Checklist

## Backend

Set APP_ENV=production, AUTH_COOKIE_SECURE=true, and AUTH_COOKIE_SAMESITE=none when the frontend and API are on different sites.
Set CORS_ORIGINS to the exact frontend origin and ALLOWED_HOSTS to the exact API hostname.
Set TRUST_PROXY_HEADERS=true only when the hosting edge is a trusted proxy.
Use a long random JWT_SECRET and managed MongoDB Atlas/Redis credentials.
Set the AI provider through AI_BASE_URL, AI_API_KEY, and AI_MODEL.
Never commit secrets.

## Health

Use /api/v1/health/live for process liveness and /api/v1/health/ready for readiness.
The application should only receive production traffic after readiness succeeds.

## Market data

Verify the NSE EOD source, BSE EOD access when enabled, NSE/BSE index feed templates when enabled, FII/FPI and DII ingestion, and the exchange holiday calendar.
Check the admin data-pipeline status before relying on daily automation.

## Security

Use HTTPS at the public edge, keep secrets in platform-managed environment variables, disable public API docs in production, and review the audit log after the first administrator login.

## CI

Merge only after GitHub Actions backend and frontend jobs pass on the pull request.
The workflow validates dependency consistency, application importability, backend tests, Python compilation, TypeScript, and the Next.js production build.

## Rollback

Keep the previous working deployment available until the new revision passes health checks and a smoke test covering login, dashboard, EOD market overview, stock intelligence, report PDF generation, and live-market connection.