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
