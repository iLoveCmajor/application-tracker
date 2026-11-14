# AGENTS.md

Guidance for AI coding agents working in this repo. Application Tracker is a single-user web app for
tracking job applications through stages, with follow-up dates and funnel numbers.

## Docs to read first

| Doc | What it holds |
| --- | --- |
| [`_docs/specs.md`](_docs/specs.md) | The spec: requirements (FR-*), data model, business rules, API, stack. Source of truth for behaviour |
| [`openapi.yaml`](openapi.yaml) | The API contract. Changed first, then the code |
| [`_docs/process.md`](_docs/process.md) | Roles, the issue lifecycle, branches and pull requests |
| [`_docs/team/pm.md`](_docs/team/pm.md) | PM role: grooming an issue |
| [`_docs/team/software-engineer.md`](_docs/team/software-engineer.md) | Engineer role: implementing an issue |
| [`_docs/team/qa-engineer.md`](_docs/team/qa-engineer.md) | QA role: verifying an issue |
| [`_docs/task-template.md`](_docs/task-template.md) | Goal / Acceptance criteria / Out of scope / Constraints |

Work is tracked in [GitHub Issues](https://github.com/iLoveCmajor/application-tracker/issues). Read
the issue with `gh issue view <n> --comments` before starting. If a task conflicts with the spec, or
the spec is ambiguous, stop and ask; don't guess.

## Commands

```sh
make install           # backend (uv) and frontend (npm) dependencies
make dev               # API on :8000 and the UI on :5173
make test              # everything: unit, API, integration (PostgreSQL), frontend
make lint              # ruff + format check
make typecheck         # mypy + tsc
docker compose up      # the whole system with PostgreSQL on http://localhost:8080
```

`make` lists every target.

## Layout

```text
backend/src/app/
  api/            FastAPI routers, request/response mapping only
  services/       business rules (status transitions, follow-ups, funnel)
  repositories/   SQL, behind the Repository protocol in base.py
  db/             engine, tables, Alembic migrations
backend/tests/
  unit/           pure tests of the rules and the funnel maths
  api/            endpoint tests through TestClient on SQLite
  integration/    the API against PostgreSQL (testcontainers, or TEST_DATABASE_URL)
frontend/src/
  api/            the typed client; the only place that calls fetch
  pages/, components/, lib/
```

## Architecture rules

- Layers: `api/` → `services/` → `repositories/`. Routers never touch SQLAlchemy.
- The rules in the spec's "Business rules" section live in pure functions in `services/` that take
  "today" as an argument, so unit tests need no database and no clock.
- Status changes only through `POST /api/v1/applications/{id}/status`, never a `PATCH`.
- A status change and its event are written in one transaction.
- Every non-2xx response uses `{"error": {"code", "message", "details"}}` with the spec's codes.
- Config comes only from environment variables (see `.env.example`). Never commit secrets or `.env`.
- Schema changes go through an Alembic migration (`make migration m="…"`).
- Logs are JSON lines with a request id. Never log request bodies or application fields.

## Backend

- FastAPI, Python 3.14, uv; code in `backend/src/app/`. Before calling a change done, run `make lint`,
  `make typecheck` and `make test`.
- `tests/api/test_contract.py` checks that the routes match `openapi.yaml`.
- Each acceptance criterion gets a test that names its id (`test_ac3_2_…`).

## Frontend

- React + TypeScript + Vite, no UI library, no router library (hash routing).
- Components never call `fetch`; all calls go through `frontend/src/api/`, typed in `types.ts`.
- Run `npm run build` and `npm test` in `frontend/` before calling a change done.

## Data

- Seed data is invented: made-up companies, no real people. Never add real job-search data, in code,
  tests, fixtures or screenshots.

## Git

- Short, plain commit messages that reference the issue (`Funnel endpoint (#5)`).
- From issue #10 on, one branch and one pull request per issue; see `_docs/process.md`.
