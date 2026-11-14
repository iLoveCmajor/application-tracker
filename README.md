# Application Tracker

A single-user web app for tracking job applications through stages, with automatic follow-up dates
and funnel numbers. Final project for [AI Dev Tools Zoomcamp 2026](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).

**Live app:** _not deployed yet_ (free tier: it sleeps after 15 minutes idle, so the first request takes about a minute)

## The problem

A job search run from a spreadsheet loses two things:

- **Follow-ups slip.** Nothing tells you that an application has been quiet for a week and deserves a
  nudge.
- **You can't tell which channel works.** A spreadsheet keeps the current status only. Once an
  application is "rejected", you no longer know whether it got as far as a screening call, so you
  can't compare cold applications with referrals or recruiter inbound.

## What the app does

- Keeps a list of applications: company, role, link, source (`cold`, `inbound`, `referral`), status,
  applied date, next follow-up date and notes. Filter the list by status.
- Moves an application through `saved → applied → screen → interview → offer`, or out to `rejected` /
  `ghosted`, with an optional note. Every change is recorded and shown as a history.
- Sets dates by itself: marking an application **applied** sets the applied date (if empty) and a
  follow-up 7 days later; **offer**, **rejected** or **ghosted** clear the follow-up.
- Shows a **Follow-ups** list: everything still in play (`applied`, `screen`, `interview`) whose
  follow-up date is today or earlier.
- Shows a **Funnel**: how many applications are in each status, and per source the share of applied
  applications that reached a screening call. An application counts as having reached screen if its
  history ever moved it to `screen` or later, even if it was rejected afterwards.

The full spec, with the data model, rules and API, is in [`_docs/specs.md`](_docs/specs.md).

### Expected behaviour, by example

1. Add "Example Robotics, Data Engineer, source: referral". It starts as `saved`, with one history
   entry.
2. Move it to `applied` on 14 Nov. Applied date becomes 14 Nov, follow-up 21 Nov.
3. On 21 Nov it shows up in **Follow-ups**. Move it to `screen`; it stays in Follow-ups until you
   change the date or the status.
4. Move it to `rejected`. The follow-up date is cleared, so it leaves Follow-ups. In **Funnel** it
   still counts for `referral` as applied *and* reached screen.
5. Moving an application to the status it already has is refused (`409 invalid_transition`); a bad
   field gets a readable message (`422 validation_error`).

## Run it

Needs Docker only:

```sh
docker compose up --build
```

Then open <http://localhost:8080>. Compose starts PostgreSQL 16 and the app, runs the migrations, and
seeds about ten invented applications so there is something to look at. `docker compose down` keeps
the data; `docker compose down -v` deletes it. If port 8080 is taken, `APP_PORT=8081 docker compose up`.

For development (needs [uv](https://docs.astral.sh/uv/) and Node.js 22):

```sh
make install   # backend and frontend dependencies
make dev       # API on :8000 (SQLite), UI on :5173 with hot reload
make test      # every test suite (needs Docker for the PostgreSQL tests)
make           # list every target
```

API docs (Swagger) are at `/docs` on a running API; the contract is [`openapi.yaml`](openapi.yaml).

## Stack and architecture

| Part | Choice |
| --- | --- |
| Backend | Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, uv |
| Database | PostgreSQL 16 (Compose, production); SQLite for the fast API tests |
| Frontend | React 19, TypeScript, Vite; no router or UI library |
| Container | one multi-stage [`Dockerfile`](Dockerfile): Node builds the UI, a slim Python image (non-root) serves the API and the built UI |
| CI/CD | GitHub Actions ([`ci.yml`](.github/workflows/ci.yml), [`smoke.yml`](.github/workflows/smoke.yml)), Render |

```text
browser ──▶ FastAPI ──┬─ /            built React app (static files)
                      ├─ /api/v1/*    api/ → services/ → repositories/ ──▶ PostgreSQL
                      └─ /health, /ready
```

- `api/` maps HTTP to calls; `services/` holds the rules as pure functions that take "today" as an
  argument; `repositories/` is the only code that touches SQL.
- A status change and its history event are written in one transaction.
- Every error is `{"error": {"code", "message", "details"}}`.
- Schema changes go through Alembic; the app migrates on start.

## Tests

`make test` runs four suites; CI runs the same ones on every pull request.

| Suite | Where | What it covers | Count |
| --- | --- | --- | --- |
| Unit | `backend/tests/unit` | date rules, follow-up rule, funnel maths, config, log format; no database | 134 |
| API | `backend/tests/api` | every endpoint through FastAPI's TestClient on SQLite, every acceptance criterion by id, the routes against `openapi.yaml` | 246 |
| Integration | `backend/tests/integration` | migrations up and down on PostgreSQL, the full flow (create → status changes → history → follow-ups → funnel), cascades, UTC timestamps | 9 |
| Frontend | `frontend/src/**/*.test.ts` | the typed API client, routing, formatting and overdue helpers (vitest) | 63 |

The integration tests start a throwaway `postgres:16` with testcontainers, or use `TEST_DATABASE_URL`
when it is set (CI uses a Postgres service container).

## CI/CD

[`ci.yml`](.github/workflows/ci.yml) runs on every pull request and every push to `main`:

1. `backend`: ruff, format check, mypy (strict), unit and API tests.
2. `frontend`: typecheck, vitest, production build.
3. `integration`: the PostgreSQL tests against a service container.
4. `docker`: builds the production image.
5. `deploy`: on `main` only, and only when 1–4 passed. Calls Render's deploy hook for that commit and
   waits until the live `/health` reports the new commit SHA. A failing test means no deploy, and the
   running version stays up.

Every change after CI existed went through a pull request with green checks
([closed pull requests](https://github.com/iLoveCmajor/application-tracker/pulls?q=is%3Apr+is%3Aclosed)).
PR #14 is a deliberately broken test that shows CI going red.

## Observability and alerting

- **Logs.** One JSON object per line on stdout, viewable in Render's log view: timestamp, level,
  message, request id, method, path, status, duration. The request id comes from `X-Request-ID` or is
  generated, and is returned in that header, so a user's report can be matched to its log line.
  Request bodies, query strings and application fields are never logged. An unhandled error logs one
  ERROR line with the request id and the traceback; the user gets a plain 500 without it.
- **Health.** `/health` says the process is up and which commit it runs; `/ready` says the database
  answers (503 if not). Render uses `/ready` as its health check.
- **Alert on user impact.** [`smoke.yml`](.github/workflows/smoke.yml) runs every hour against the
  public URL and checks what a user needs: the app is up, the database answers, and the funnel page's
  API returns data. It retries for up to four minutes so a sleeping free instance can wake. On
  failure it opens a GitHub issue labelled
  [`alert`](https://github.com/iLoveCmajor/application-tracker/issues?q=label%3Aalert), or comments on
  the one already open.

Metrics, traces and an on-call agent are out of scope for this project.

## Deployment

The app runs on [Render](https://render.com): a free web service built from the root `Dockerfile`,
with a free Render Postgres. [`render.yaml`](render.yaml) describes both. Render's own auto-deploy is
off; the `deploy` job in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) deploys instead. It
runs only on a push to `main`, only after every other CI job has passed, calls the Render deploy hook
for that commit, then polls `/health` until `version` equals the pushed SHA (up to 10 minutes).
Until the secret and the variable below exist, the job skips with a notice and `main` stays green.

Owner setup, once:

1. In the Render dashboard: **New → Blueprint**, connect the `iLoveCmajor/application-tracker`
   repository, branch `main`. Render reads `render.yaml` and creates the `application-tracker` web
   service and the `application-tracker-db` database. Apply it.
2. Open the web service → **Settings**. Check that **Auto-Deploy** is **Off** (the Blueprint sets it).
   Copy the **Deploy Hook** URL. It is a secret: don't paste it anywhere else.
3. In GitHub, **Settings → Secrets and variables → Actions**:
   - **Secrets** tab → New repository secret `RENDER_DEPLOY_HOOK_URL` = the deploy hook URL.
   - **Variables** tab → New repository variable `APP_URL` = the service URL, e.g.
     `https://application-tracker-xxxx.onrender.com` (no trailing slash needed).
4. Re-run the latest CI run on `main` (or push to `main`). The `deploy` job should end with
   "`/health` reports version <sha>".
5. Replace the **Live app** line at the top of this README with the URL.

Free tier limits:

- The web service sleeps after 15 minutes without traffic; the next request wakes it, which takes
  about a minute.
- A free Render Postgres expires 30 days after it is created (Render deletes it after a grace period
  unless it is upgraded). To keep a free database, create a new one from the Blueprint and point the
  service at it; the demo data is seeded again on the next start.

`/health` reports the deployed commit from `RENDER_GIT_COMMIT`, which Render sets on every deploy.

## How it was built

Built with AI coding agents (Claude Code) following the course's PM → Engineer → QA process. What
actually happened:

1. **Plan and spec first.** Vladimir wrote the plan: scope, points target, order of work and cut
   lines. From it came [`_docs/specs.md`](_docs/specs.md) (requirements FR-1…FR-10, data model,
   business rules, API) and [`openapi.yaml`](openapi.yaml), before any code.
2. **Context for the agents.** [`AGENTS.md`](AGENTS.md) holds the commands, layout and architecture
   rules and links the modular docs below. `CLAUDE.md` just imports it.
3. **Backlog in GitHub Issues.** One issue per task
   ([all issues](https://github.com/iLoveCmajor/application-tracker/issues?q=is%3Aissue)).
4. **The agent team** ([`_docs/process.md`](_docs/process.md)). The main session is the
   orchestrator. For each issue it starts three separate subagents, each with a fresh context:
   - **PM** ([`pm.md`](_docs/team/pm.md)) rewrites the issue into
     [`task-template.md`](_docs/task-template.md): goal, acceptance criteria with ids (`AC-3.2`), out
     of scope, constraints. Comments `## PM: groomed`.
   - **Engineer** ([`software-engineer.md`](_docs/team/software-engineer.md)) implements it with tests
     named after the criteria, commits (or opens a pull request), comments `## Engineer: done`.
   - **QA** ([`qa-engineer.md`](_docs/team/qa-engineer.md)) checks every criterion against the running
     code (curl, Playwright in a browser, Docker), never fixes anything, and posts `## QA: PASS` or
     `## QA: FAIL` with evidence.
   - The orchestrator closes an issue only on PASS. A FAIL goes back to a fresh engineer: issue
     [#2](https://github.com/iLoveCmajor/application-tracker/issues/2) failed QA once (date fields
     accepted numbers) and passed on the retry. QA also found bugs outside the criteria, which became
     new issues ([#15](https://github.com/iLoveCmajor/application-tracker/issues/15),
     [#18](https://github.com/iLoveCmajor/application-tracker/issues/18)).
5. **What a human did.** Vladimir wrote the plan, owns the Render account and the GitHub secrets
   (agents never touch credentials), reviewed the result and clicked through the deployed app.

## Repository map

| Path | What |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | entry point for coding agents |
| [`_docs/specs.md`](_docs/specs.md) | the spec |
| [`_docs/process.md`](_docs/process.md), [`_docs/team/`](_docs/team) | agent roles and process |
| [`openapi.yaml`](openapi.yaml) | API contract |
| `backend/` | FastAPI app, migrations, tests |
| `frontend/` | React app and its tests |
| [`Dockerfile`](Dockerfile), [`compose.yaml`](compose.yaml) | image and the local full system |
| [`render.yaml`](render.yaml) | Render Blueprint |
| `.github/workflows/` | CI/CD and the smoke-check alert |
| `scripts/` | smoke check and alert scripts used by the workflow |
