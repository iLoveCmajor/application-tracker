#!/usr/bin/env bash
# Opens an issue labelled `alert` for a failed smoke check, or comments on the open one if there is
# one, so repeated failures stay in a single thread. Run by .github/workflows/smoke.yml.
#
# Env: FAILED_CHECK (e.g. /ready), DETAIL (its last error), TARGET_URL, RUN_URL (the workflow run),
# GH_TOKEN and GH_REPO (or a checkout gh can read the repo from).
set -euo pipefail

check="${FAILED_CHECK:-unknown check}"
message="Smoke check \`$check\` failed on ${TARGET_URL:-the app}: ${DETAIL:-no detail}.

Run: ${RUN_URL:-unknown}"

open_alert="$(gh issue list --label alert --state open --limit 1 --json number --jq '.[0].number // empty')"
if [[ -n "$open_alert" ]]; then
  gh issue comment "$open_alert" --body "$message"
  echo "commented on open alert #$open_alert"
else
  gh issue create --label alert --title "Smoke check failed: $check" --body "$message

Later failures are added here as comments until this issue is closed."
  echo "opened a new alert issue"
fi
