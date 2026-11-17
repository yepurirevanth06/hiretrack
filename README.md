# HireTrack

![CI](https://github.com/yepurirevanth06/hiretrack/actions/workflows/ci.yml/badge.svg)

A backend for a multi-company hiring platform: companies post jobs, candidates keep a resume library and apply, and recruiters move applications through a hiring pipeline.

Built with **Python, FastAPI, PostgreSQL, SQLAlchemy 2.0 and Alembic**, with a focus on correctness under concurrency and performance at scale.

## Features

- Companies, jobs, candidates, resumes and applications (15 REST endpoints)
- Each application keeps a snapshot of the exact resume it was submitted with
- Application pipeline as a state machine: applied, screening, interview, offer, hired, rejected, withdrawn
- Closing a job rejects every active application in a single transaction
- Cursor (keyset) pagination with an optional total count
- Consistent JSON error responses (400, 404, 409, 422, 503)

## Architecture

```
Request -> Route (HTTP only) -> Service (business rules, transactions) -> Repository (queries) -> PostgreSQL
```

| Layer | Folder | Responsibility |
|---|---|---|
| Schemas | `app/schemas/` | Request and response validation (Pydantic) |
| Routes | `app/api/routes/` | HTTP: parse the request, call a service, return a response |
| Services | `app/services/` | Business rules and transaction boundaries |
| Repositories | `app/repositories/` | Database queries |
| Models | `app/models/` | SQLAlchemy tables, constraints and indexes |

## Key design decisions

- **Duplicate applications are blocked by a database unique constraint**, not only an application check, so concurrent requests cannot create duplicates.
- **Status changes lock the row** (`SELECT ... FOR UPDATE`) so two recruiters cannot overwrite each other's changes.
- **Applying takes a shared lock on the job** (`FOR SHARE`), so an application cannot slip in while the job is being closed.
- **Status updates and job closing are idempotent**, so retried requests are safe.
- **Business rules live in pure functions where possible** (the state machine), so they can be unit tested without a database.

## Security

- **Password storage:** Argon2 hashing via `pwdlib`; plain passwords are never stored or logged.
- **Authentication:** short-lived JWT access tokens (HS256, 15 min expiry). Tokens require `exp` and `sub`, carry a `type: access` claim, and are decoded against an explicit algorithm allow-list.
- **User enumeration protection:** login returns the same error for an unknown email and a wrong password, and verifies against a dummy hash when the user doesn't exist, so response timing doesn't reveal which emails are registered.
- **Role-based access:** candidate and recruiter roles are enforced through FastAPI dependencies (`CurrentUser`, `CurrentRecruiter`, `CurrentCandidate`).
- **Multi-tenancy:** recruiters are scoped to their own company via `company_id`; database check constraints guarantee every recruiter has a company and every candidate has a profile.
- **IDOR prevention:** identity always comes from the token, never from the request body. Candidates use `/me` routes, and `candidate_id` was removed from the apply payload.
- **Visibility policy:** 404 when the caller can't see a resource (so its existence isn't leaked), 403 when they can see it but aren't allowed to act on it. Draft and closed jobs are hidden from the public.
- **Workflow permissions:** only the candidate can withdraw an application; only the company's recruiter can move it through screening, interview, offer, hired, or rejected.
- **Refresh tokens:** 7-day opaque tokens stored only as SHA-256 hashes. Every refresh rotates the token, and replaying an already-used token revokes that whole session (token family), which shuts out a thief who copied it.
- **Logout:** `/auth/logout` ends one session, `/auth/logout-all` ends every session for the user. A row lock on the token prevents two simultaneous refreshes from both succeeding.
- **Audit log:** logins, logouts, token reuse, application status changes and job closures are written to `audit_events` in the same transaction as the change, so a change is never saved without its audit row. A database trigger rejects any UPDATE or DELETE, making the log append-only. `GET /applications/{id}/history` shows an application's timeline.
- **Error contract:** 401 responses include a `WWW-Authenticate: Bearer` header.
- **Row-level security:** every request runs as a restricted `hiretrack_app` database role with the user's company or candidate id set for that transaction. A PostgreSQL policy on `applications` hides other tenants' rows, so a missing permission check in Python still can't leak data.
- **Least privilege:** the app role can't update or delete audit rows, can't truncate tables and isn't a table owner, so it can't switch RLS off.
- **CORS and security headers:** only configured browser origins may call the API, and every response sets `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Cache-Control: no-store` and `Strict-Transport-Security`.
- **OWASP review:** see [docs/security-review.md](docs/security-review.md) for what is covered and what is still missing.

## Performance

Measured locally on **1,000,000 jobs and 300,050 applications** using `EXPLAIN ANALYZE`.

| Problem | Before | After | Fix |
|---|---|---|---|
| Latest jobs query | 32 ms (full scan + sort) | 0.05 ms (backward index scan) | Composite index matching the `ORDER BY` |
| Page at position 90,000 | 126 ms (sort spilled to disk) | 0.04 ms | Cursor pagination instead of `OFFSET` |
| Candidate's applications | 56 queries, ~22 ms | 2 queries, ~7 ms | Eager loading (fixed N+1) |
| First page of open jobs | ~10 ms | ~5 ms | Total count made opt-in |

## Running locally

Requirements: Docker and [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

API docs: http://localhost:8000/docs

## Tests

```bash
docker compose exec db psql -U hiretrack -d hiretrack -c "CREATE DATABASE hiretrack_test;"
uv run pytest --cov=app
```

130 unit and integration tests run against an isolated PostgreSQL database. Each test runs inside a transaction that is rolled back afterwards, and anything a request doesn't commit is discarded, just like in production. CI runs linting, migrations, a migration drift check and the full test suite on every push and pull request.

## Roadmap

- [x] Stage 1: Core API, data modeling, testing, query performance
- [x] Stage 2: Security: authentication, authorization, multi-tenancy, refresh token rotation, audit log, row-level security, CORS, security headers
- [ ] Stage 3: Caching, rate limiting and load testing
- [ ] Stage 4: Background jobs, file uploads and notifications
- [ ] Stage 5: Search, AI matching and observability
- [ ] Stage 6: Microservices and event streaming
- [ ] Stage 7: Scaling and cloud deployment
