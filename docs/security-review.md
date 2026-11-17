# HireTrack security review (OWASP Top 10, 2021)

A pass over the whole API against the OWASP Top 10. Each item lists what is in
place today, where it lives, and what is still missing.

## A01 Broken Access Control

**In place**
- Roles (candidate, recruiter) are enforced by FastAPI dependencies (`app/api/deps.py`).
- Recruiters are scoped to their own company; candidates use `/me` routes, and identity always comes from the token, never from ids in the request body (IDOR prevention).
- 404 when the caller can't see a resource, 403 when they can see it but can't act on it, so the API doesn't reveal what exists.
- **Second layer in the database:** every request runs as the restricted `hiretrack_app` role with PostgreSQL row-level security on `applications`. Even if a Python permission check is removed by mistake, the database still hides other tenants' rows (`tests/test_rls.py` proves this by disabling the check).

**Gaps**
- RLS covers `applications` only. `resumes` and draft `jobs` still rely on the service layer.

## A02 Cryptographic Failures

**In place**
- Passwords hashed with Argon2 (`pwdlib`). Refresh tokens stored only as SHA-256 hashes.
- JWTs are signed with a secret from the environment; the algorithm list is pinned, so `alg: none` and algorithm-switching attacks are rejected.
- `Strict-Transport-Security` tells browsers to use HTTPS only.

**Gaps**
- TLS itself has to be terminated by a proxy or load balancer in front of the app; nothing in this repo sets that up yet.

## A03 Injection

**In place**
- All queries go through SQLAlchemy with bound parameters. The one place that builds SQL text (`SET LOCAL` in `app/db/tenant.py`) only accepts integers and converts them with `int()` first.
- Every request body is validated by Pydantic (types, lengths, slug pattern).
- `Content-Security-Policy: default-src 'none'` and `X-Content-Type-Options: nosniff` stop a JSON response from being run as a script or page.

## A04 Insecure Design

**In place**
- The application workflow is an explicit state machine; invalid moves return 409.
- Uniqueness and data rules are database constraints (unique, check, foreign keys), not just Python checks, so race conditions can't break them.
- Row locks (`SELECT ... FOR UPDATE`) prevent lost updates and double use of a refresh token.

## A05 Security Misconfiguration

**In place**
- Security headers on every response, including errors (`app/core/middleware.py`).
- CORS allows only configured origins (`CORS_ORIGINS`), and credentials mode is off.
- `JWT_SECRET` has no default: the app refuses to start without one.

**Gaps**
- Swagger UI (`/docs`) is public. In production it should be disabled or put behind auth.

## A06 Vulnerable and Outdated Components

**In place**
- Dependencies are pinned in `uv.lock`, and CI installs exactly those versions (`uv sync --locked`).

**Gaps**
- No automated vulnerability scan yet (for example `pip-audit` in CI, or Dependabot).

## A07 Identification and Authentication Failures

**In place**
- Same error message and similar timing for "unknown email" and "wrong password" (dummy hash), so emails can't be discovered.
- 15-minute access tokens; 7-day refresh tokens with rotation and reuse detection; logout and logout from all devices.
- Deactivated users are rejected on every request and on refresh.

**Gaps**
- No rate limiting or lockout on `/auth/token`, so password guessing isn't throttled (planned for Stage 3).
- No password breach check and no MFA.
- An access token stays valid until it expires (up to 15 minutes) after logout.

## A08 Software and Data Integrity Failures

**In place**
- The audit log is append-only twice over: a trigger rejects UPDATE and DELETE, and the app role has no UPDATE or DELETE privilege on it.
- Audit rows are written in the same transaction as the change, so a change can't be saved without its record.
- CI checks that migrations match the models (`alembic check`).

## A09 Security Logging and Monitoring Failures

**In place**
- `audit_events` records logins, logouts, refresh token reuse, application status changes and job closures, with the acting user.

**Gaps**
- Failed logins aren't recorded, and nothing alerts on suspicious events such as token reuse (planned with observability in Stage 5).

## A10 Server-Side Request Forgery

**In place**
- The API never fetches a URL supplied by a user. Resumes are stored as file keys, not downloaded from links.

**Watch for**
- File uploads (Stage 4) must not fetch remote URLs on the user's behalf.
