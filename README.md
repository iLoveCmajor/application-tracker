# Application Tracker

A single-user web app for tracking job applications through stages, with automatic follow-up dates
and funnel numbers. Final project for [AI Dev Tools Zoomcamp 2026](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).

**Live app:** _coming in a later stage_

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
