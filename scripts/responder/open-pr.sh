#!/usr/bin/env bash
# Pushes the verified fix to responder/alert-<n> and opens a pull request for it (#26). Run by the
# workflow, never by the model, in a clean checkout of the commit the model worked on.
#
#   scripts/responder/open-pr.sh 42 out/
#
# Reads out/patch.diff, out/result.json and out/verdict.json. Prints the pull request URL, and
# writes it to $GITHUB_OUTPUT as `url` under Actions. A pull request opened with the workflow's
# GITHUB_TOKEN starts no CI run, so the body says so and which tests the responder ran itself.
#
# Env: GH_TOKEN and GH_REPO (or a checkout gh can read the repo from), RUN_URL, BASE_BRANCH
# (default main), PUSH_REMOTE (default origin).
set -euo pipefail

issue="${1:-}"
out="${2:-}"
if [[ ! "$issue" =~ ^[0-9]+$ || -z "$out" ]]; then
  echo "usage: $0 <issue-number> <out-dir>" >&2
  exit 2
fi
if [[ "$(jq -r .decision "$out/verdict.json")" != "pr" ]]; then
  echo "the verdict is not \"pr\"; nothing to open" >&2
  exit 1
fi
here="$(cd "$(dirname "$0")" && pwd)"
base="${BASE_BRANCH:-main}"
remote="${PUSH_REMOTE:-origin}"
branch="responder/alert-$issue"

# The same allowlist verify.sh enforces. Checked again here, on the patch itself, because the
# artifact travelled between jobs and verify.sh's verdict is only a claim about it.
allowed='^(backend/src/|backend/tests/|frontend/src/)'
refuse() {
  echo "refusing to open a pull request: $1" >&2
  exit 1
}
numstat="$(git apply --numstat "$out/patch.diff")" || refuse "the patch does not read"
paths="$(cut -f3- <<<"$numstat")"
[[ -n "$paths" ]] || refuse "the patch is empty"
grep -qF ' => ' <<<"$paths" && refuse "the patch renames files"
outside="$(grep -Ev "$allowed" <<<"$paths" || true)"
[[ -z "$outside" ]] || refuse "the patch touches files outside the allowed paths: $(tr '\n' ' ' <<<"$outside")"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git checkout -B "$branch"
git apply --index "$out/patch.diff"
# What is actually staged, against what verify.sh said it checked.
staged="$(git diff --cached --name-only --no-renames HEAD | sort)"
[[ -z "$(grep -Ev "$allowed" <<<"$staged" || true)" ]] || refuse "the applied patch touches files outside the allowed paths"
[[ "$staged" == "$(jq -r '.changed[]' "$out/verdict.json" | sort)" ]] || refuse "the patch does not match the verified file list"
git commit --quiet -m "Responder fix for alert #$issue" -m "$(jq -L "$here" -r 'include "safe"; .cause | safe' "$out/result.json")"
# The branch belongs to the responder; a later run on the same alert replaces it.
git push --force "$remote" "HEAD:refs/heads/$branch"

tests="$(jq -r '.tests[] | "- `\(.command)`: \(if .passed then "passed" else "failed" end)"' "$out/verdict.json")"
files="$(jq -r '.changed[] | "- `\(.)`"' "$out/verdict.json")"
# A test file is anything under backend/tests/ or a frontend .test.ts / .test.tsx (#37).
test_files="$(jq -r '.changed[] | select(test("^backend/tests/|^frontend/src/.*\\.test\\.tsx?$")) | "`\(.)`"' "$out/verdict.json" | paste -sd, - | sed 's/,/, /g')"
body_file="$(mktemp)"
trap 'rm -f "$body_file"' EXIT
# Text from the model goes in with @ defused, so it can't mention anyone.
jq -L "$here" -r --arg issue "$issue" --arg run "${RUN_URL:-unknown}" --arg tests "$tests" --arg files "$files" --arg testfiles "$test_files" '
  include "safe";
  "Proposed by the on-call responder for alert #\($issue). Refs #\($issue).\n\n" +
  "**Cause:** \(.cause | safe)\n\n" +
  "**Fix:** \(.fix | safe)\n\n" +
  "**Changed files:**\n\($files)\n\n" +
  (if $testfiles == "" then "" else
    "**Test files changed:** \($testfiles). A changed test can make \"tests passed\" meaningless, so read these files first.\n\n" end) +
  "**Tests the responder ran on this change (all passed):**\n\($tests)\n\n" +
  "The integration tests (PostgreSQL) did not run here.\n\n" +
  "**CI did not start automatically**: this pull request was opened with the workflow'"'"'s " +
  "`GITHUB_TOKEN`, which starts no other workflows. Push a commit to `responder/alert-\($issue)` " +
  "or close and reopen this pull request to run CI before merging.\n\n" +
  "A human reviews and merges; the responder never merges or deploys.\n\n" +
  "Model: \(.model). Run: \($run)"' "$out/result.json" >"$body_file"

existing="$(gh pr list --head "$branch" --state open --json url --jq '.[0].url // empty')"
if [[ -n "$existing" ]]; then
  url="$existing"
  gh pr comment "$url" --body-file "$body_file" >/dev/null
else
  url="$(gh pr create --base "$base" --head "$branch" \
    --title "Responder: fix for alert #$issue" --body-file "$body_file" | tail -n 1)"
fi
echo "$url"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "url=$url" >>"$GITHUB_OUTPUT"
fi
