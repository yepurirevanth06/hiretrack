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

67 unit and integration tests run against an isolated PostgreSQL database. Each test runs inside a transaction that is rolled back afterwards. CI runs linting, migrations, a migration drift check and the full test suite on every push and pull request.

## Roadmap

- [x] Stage 1: Core API, data modeling, testing, query performance
- [ ] Stage 2: Authentication, roles and multi-tenant data isolation
- [ ] Stage 3: Caching, rate limiting and load testing
- [ ] Stage 4: Background jobs, file uploads and notifications
- [ ] Stage 5: Search, AI matching and observability
- [ ] Stage 6: Microservices and event streaming
- [ ] Stage 7: Scaling and cloud deployment
