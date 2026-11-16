#!/usr/bin/env bash
# Opens an issue labelled `alert` for a failed smoke check, or comments on the open one if there is
# one, so repeated failures stay in a single thread. Run by .github/workflows/smoke.yml.
#
# A new alert also starts the on-call responder (#26) with `gh workflow run`: an issue opened with
# GITHUB_TOKEN fires no `issues` event, but a workflow_dispatch does start a run. A comment on an
# alert that is already open does not start it again.
#
# Env: FAILED_CHECK (e.g. /ready), DETAIL (its last error), TARGET_URL, RUN_URL (the workflow run),
# GITHUB_RUN_ID (passed to the responder so it can read this run's log), RESPONDER_WORKFLOW
# (default responder.yml; empty to not start it), GH_TOKEN and GH_REPO (or a checkout gh can read
# the repo from).
set -euo pipefail

check="${FAILED_CHECK:-unknown check}"
message="Smoke check \`$check\` failed on ${TARGET_URL:-the app}: ${DETAIL:-no detail}.

Run: ${RUN_URL:-unknown}"

open_alert="$(gh issue list --label alert --state open --limit 1 --json number --jq '.[0].number // empty')"
if [[ -n "$open_alert" ]]; then
  gh issue comment "$open_alert" --body "$message"
  echo "commented on open alert #$open_alert"
else
  url="$(gh issue create --label alert --title "Smoke check failed: $check" --body "$message

Later failures are added here as comments until this issue is closed.")"
  number="${url##*/}"
  echo "opened a new alert issue: $url"
  responder="${RESPONDER_WORKFLOW-responder.yml}"
  if [[ -n "$responder" && "$number" =~ ^[0-9]+$ ]]; then
    if gh workflow run "$responder" -f issue="$number" -f smoke_run_id="${GITHUB_RUN_ID:-}" \
      -f url="${TARGET_URL:-}"; then
      echo "started the responder for #$number"
    else
      echo "::warning::Could not start the responder for #$number; add the alert label again to start it."
    fi
  fi
fi
