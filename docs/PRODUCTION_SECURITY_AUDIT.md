# Production Readiness & Security Audit

**Repository:** ShareM Int Xpo  
**Audit date:** 2026-10-09  
**Scope:** Static review of repository configuration and selected backend/frontend security files. This is not a penetration test, dependency vulnerability scan, or verified production deployment.

## Executive summary

The project has several useful foundations: password hashing with scrypt, short-lived signed access tokens, refresh tokens stored in HttpOnly cookies, email verification, optional TOTP, MongoDB TTL/unique indexes, request IDs, security response headers, trusted-host validation, and rate-limited authentication/admin endpoints.

The repository should not be considered production-ready solely from these controls. Runtime tests, dependency scanning, deployment configuration review, secret scanning, and a staging smoke test are still required.

## Findings

### P1 — Production API documentation can remain enabled
**Evidence:** `backend/app/core/config.py` defaults `DOCS_ENABLED` to true and the production validator did not require it to be false. `backend/app/main.py` uses this setting to expose Swagger, ReDoc, and OpenAPI.

**Risk:** Public API schemas expose route structure and request/response models, which increases reconnaissance surface.

**Fix:** Production startup now fails when `DOCS_ENABLED=true`. Set `DOCS_ENABLED=false` in production.

### P1 — Production JWT secret accepts recognizable placeholder values if sufficiently long
**Evidence:** Production validation previously checked only the JWT secret length.

**Risk:** A deployment can accidentally use a predictable template secret and still pass startup validation.

**Fix:** Production startup now rejects common placeholder strings in addition to enforcing minimum length. Use a cryptographically random secret from a managed secret store.

### P1 — Authentication throttling is primarily client-IP scoped
**Evidence:** `backend/app/api/deps/rate_limit.py` keys limits by scope, client IP, and time window. Login uses this limiter.

**Risk:** Distributed attempts against one account may evade per-IP limits. If proxy trust is enabled without a trusted-edge guarantee, spoofed forwarding headers can also undermine client-IP identification.

**Recommendation:** Add account-identifier throttling for login and verification flows, progressive delay/temporary lockout with safe recovery, and only enable `TRUST_PROXY_HEADERS` behind a known reverse proxy that overwrites forwarding headers.

### P1 — No verified current CI/test result in this audit
**Evidence:** Repository documentation describes CI checks, but a current successful workflow run and full runtime test suite were not verified during this review.

**Risk:** Static inspection cannot prove correct behavior under malformed requests, database outages, concurrency, or deployment configuration.

**Recommendation:** Run CI and security checks on the proposed branch; add regression tests for production settings and auth failure cases.

### P2 — Runtime configuration needs deployment-specific review
**Evidence:** CORS, host validation, cookie settings, proxy trust, Redis, SMTP, and external providers are environment-configured.

**Risk:** Incorrect values can cause insecure cookies, broken session rotation, overly permissive trust boundaries, or unavailable background features.

**Recommendation:** Use explicit production values; keep provider/database credentials in the deployment secret manager; validate the exact deployed origins and hostnames.

### P2 — Rate-limit storage and database availability are security dependencies
**Evidence:** Rate limiting uses MongoDB atomic updates. The MongoDB lifespan establishes indexes and starts background workers.

**Risk:** Database outages can affect auth endpoints and startup availability. TTL cleanup is asynchronous and must not be treated as an exact-time lockout mechanism.

**Recommendation:** Test startup and endpoint behavior during database failure, verify unique/TTL indexes on the deployed database, and alert on repeated startup or rate-limit storage errors.

### P2 — Security headers are present, but Content Security Policy is not configured
**Evidence:** Frontend `next.config.ts` sets several useful browser security headers, but no Content-Security-Policy header is configured.

**Risk:** Missing CSP removes an additional browser-side mitigation against script injection. A strict policy must be tested against Next.js runtime behavior before enforcement.

**Recommendation:** Introduce a tested CSP in report-only mode first, then enforce a policy that fits the actual frontend and any required external providers.

### P2 — Market-data and AI behavior require operational validation
**Evidence:** The README documents NSE/BSE ingestion, yfinance supplementation, AI gateway settings, and a scheduler.

**Risk:** A configured source is not proof of current, complete, licensed, or correctly timestamped market data. AI output must not be represented as guaranteed financial advice.

**Recommendation:** Test source timestamps, duplicate/replayed payloads, stale-data labeling, upstream timeout/size limits, provider failure handling, and evidence traceability. Clearly label delayed/unavailable feeds and analytical limitations.

## Positive controls observed

- Passwords are hashed with scrypt and compared with constant-time digest comparison.
- Refresh tokens are random, stored as hashes in the database, and issued as HttpOnly cookies.
- Access tokens are short-lived and tied to server-side sessions.
- Email verification and optional TOTP are implemented.
- Admin operations use permission dependencies and audit logging.
- CORS is configured with an explicit origin list; trusted-host middleware is present.
- Security headers and request correlation IDs are implemented.
- MongoDB unique and TTL indexes cover several security/session collections.
- Frontend has baseline anti-framing, MIME-sniffing, referrer, and permissions headers.

## Release gate checklist

- [ ] Set production secrets through managed environment variables; rotate any credential ever committed.
- [ ] Set `APP_ENV=production`, `DOCS_ENABLED=false`, `AUTH_COOKIE_SECURE=true`, exact `CORS_ORIGINS`, and exact `ALLOWED_HOSTS`.
- [ ] Configure proxy trust only when the deployment edge sanitizes forwarding headers.
- [ ] Run backend tests, Python compilation, frontend type-check, and production build.
- [ ] Run dependency audit and secret scan; review and remediate all high/critical findings.
- [ ] Test login, verification, refresh rotation, logout/revocation, TOTP, role enforcement, and CSRF rejection.
- [ ] Test database/Redis/AI-provider outages and ingestion timeout/size limits.
- [ ] Verify HTTPS, cookies, CORS, health/readiness endpoints, backups, alerts, and rollback on staging.
- [ ] Review exchange data licensing/access terms and financial-risk disclosures before public launch.

## Status

**Preliminary result: Not yet certified production-ready.** This review identified concrete hardening changes and additional release gates. Completion of this document does not mean the system has been penetration-tested or deployed.


## Additional finding discovered during implementation

### P1 — RBAC endpoints could permit privilege escalation
**Evidence:** The role-management endpoints accepted permission lists, and the user-role endpoint could assign the reserved `admin` role to an actor who merely held the `admin.users.manage` permission. A delegated role manager could also create a role with wildcard or administrative permissions and potentially have it assigned.

**Branch remediation:** Non-admin actors are now blocked from creating/updating roles with wildcard or `admin.*` permissions and cannot assign the reserved admin role or any role containing administrative permissions. The actual `admin` role retains its intended management behavior. Regression tests were added for these checks.

## Branch remediation status

The audit branch now includes the following configuration/RBAC hardening:
- Production startup rejects enabled API documentation.
- Production startup rejects common placeholder JWT secret strings.
- Production CORS origins must use HTTPS.
- Non-admin RBAC actors cannot grant wildcard/admin permissions or assign privileged roles.
- Failed login attempts are additionally rate-limited by a keyed HMAC of the normalized email, in addition to the existing per-IP limit; raw email addresses are not stored in rate-limit keys.
- Regression tests cover production configuration, RBAC protections, and rate-limit threshold behavior.

These changes are committed on `security/production-readiness-audit`; they are not a substitute for completed CI, staging, or penetration testing.
