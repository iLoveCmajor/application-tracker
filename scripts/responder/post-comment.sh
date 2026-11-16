#!/usr/bin/env bash
# Posts the responder's one comment on the alert issue (#26): diagnosis, what happened to any fix,
# the evidence summary and the run link. Run by the workflow, never by the model.
#
#   scripts/responder/post-comment.sh 42 out/
#
# Reads out/result.json, out/verdict.json and out/summary.md when they exist; a run that died
# before them still gets a comment that sends a human to the run log.
#
# Env: GH_TOKEN and GH_REPO (or a checkout gh can read the repo from), RUN_URL, PR_URL (the pull
# request open-pr.sh opened, if any), PR_RESULT (that job's result, e.g. failure),
# COMMENT_DRY_RUN=1 (print the comment instead of posting it).
set -euo pipefail

issue="${1:-}"
out="${2:-}"
if [[ ! "$issue" =~ ^[0-9]+$ || -z "$out" ]]; then
  echo "usage: $0 <issue-number> <out-dir>" >&2
  exit 2
fi
here="$(cd "$(dirname "$0")" && pwd)"
run_url="${RUN_URL:-unknown}"
pr_url="${PR_URL:-}"

field() { jq -L "$here" -r --arg k "$1" 'include "safe"; .[$k] // "" | tostring | safe' "$out/result.json"; }

body="$(mktemp)"
trap 'rm -f "$body"' EXIT

if [[ ! -s "$out/result.json" ]]; then
  {
    echo "## Responder: no diagnosis"
    echo
    echo "The responder run failed before the model gave a result. **A human needs to look at this alert.**"
  } >"$body"
else
  category="$(jq -r .category "$out/result.json")"
  decision="$(jq -r '.decision // "none"' "$out/verdict.json" 2>/dev/null || echo none)"
  reason="$(jq -r '.reason // ""' "$out/verdict.json" 2>/dev/null || true)"
  case "$category" in
    code) title="likely a code problem" ;;
    infra) title="not a code problem, a human needs to act" ;;
    *) title="cause unclear, a human needs to act" ;;
  esac
  if jq -e '.reachable == false' "$out/facts.json" >/dev/null 2>&1; then
    title="the app does not answer, a human needs to act"
  fi
  {
    echo "## Responder: $title"
    echo
    echo "**Cause:** $(field cause)"
    echo
    summary="$(field summary)"
    if [[ -n "$summary" ]]; then
      echo "$summary"
      echo
    fi
    if [[ "$decision" == "pr" && -n "$pr_url" ]]; then
      echo "**Fix proposed:** $pr_url. $(field fix)"
      echo
      echo "Tests the responder ran on it:"
      jq -r '.tests[] | "- `\(.command)`: \(if .passed then "passed" else "failed" end)"' "$out/verdict.json"
      echo
      echo "CI did not start on that pull request by itself (it was opened with \`GITHUB_TOKEN\`): push to the branch or close and reopen it to run CI. A human reviews and merges."
    elif [[ "$decision" == "pr" ]]; then
      echo "**No pull request:** the fix passed its tests, but opening the pull request failed (${PR_RESULT:-unknown}); see the run. **A human needs to act.**"
    else
      echo "**No pull request:** $reason."
      if [[ "$category" == "code" ]] && jq -e '.tests | length > 0' "$out/verdict.json" >/dev/null 2>&1; then
        echo
        echo "Tests the responder ran on the proposed change:"
        jq -r '.tests[] | "- `\(.command)`: \(if .passed then "passed" else "failed" end)"' "$out/verdict.json"
      fi
      echo
      action="$(field human_action)"
      echo "**A human needs to act:** ${action:-read the evidence and the run log.}"
    fi
  } >"$body"
fi

{
  echo
  echo "<details><summary>Evidence (collected by a script before the model ran)</summary>"
  echo
  if [[ -s "$out/summary.md" ]]; then cat "$out/summary.md"; else echo "- not collected"; fi
  echo
  echo "</details>"
  echo
  model="$(jq -r '.model // empty' "$out/result.json" 2>/dev/null || true)"
  echo "Run: $run_url${model:+ · model: $model}"
} >>"$body"

if [[ "${COMMENT_DRY_RUN:-}" == "1" ]]; then
  cat "$body"
else
  gh issue comment "$issue" --body-file "$body"
fi
