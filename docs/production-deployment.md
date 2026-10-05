# Production Deployment Checklist

## Backend

Set APP_ENV=production, AUTH_COOKIE_SECURE=true, and AUTH_COOKIE_SAMESITE=none when the frontend and API are on different sites.
Set CORS_ORIGINS to the exact frontend origin and ALLOWED_HOSTS to the exact API hostname.
Set TRUST_PROXY_HEADERS=true only when the hosting edge is a trusted proxy.
Use a long random JWT_SECRET and managed MongoDB Atlas/Redis credentials.
Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM for production email verification. SMTP_PORT 587 with STARTTLS is the default path.
Set the AI provider through AI_BASE_URL, AI_API_KEY, and AI_MODEL.
Never commit secrets.

## Health

Use /api/v1/health/live for process liveness and /api/v1/health/ready for readiness.
The application should only receive production traffic after readiness succeeds.
Verify registration sends an email, `/api/v1/auth/verify` accepts the code, and `/api/v1/auth/resend-verification` is rate-limited and functional.

## Market data

Verify the NSE EOD source, BSE EOD access when enabled, NSE/BSE index feed templates when enabled, FII/FPI and DII ingestion, and the exchange holiday calendar.
Check the admin data-pipeline status before relying on daily automation.

## Security

Use HTTPS at the public edge, keep secrets in platform-managed environment variables, disable public API docs in production, and review the audit log after the first administrator login.

## CI

Merge only after GitHub Actions backend and frontend jobs pass on the pull request.
The workflow validates dependency consistency, production configuration importability, backend tests, Python compilation, the backend production image, TypeScript, and the Next.js production build. The separate Security workflow runs CodeQL and high-severity dependency review.

## Rollback

Keep the previous working deployment available until the new revision passes health checks and a smoke test covering login, dashboard, EOD market overview, stock intelligence, report PDF generation, and live-market connection.