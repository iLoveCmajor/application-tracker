#!/usr/bin/env bash
# Decides, in code, whether the model's change may become a pull request (#26). Run in the checkout
# the model worked in, after it.
#
#   scripts/responder/verify.sh out/
#
# Reads out/result.json and out/facts.json; writes out/verdict.json, out/patch.diff and
# out/tests.log. A pull request is proposed only when all of these hold:
#   - the model classified the alert as `code`
#   - the app answered at all (an unreachable host is never treated as a code problem)
#   - files changed, and only under backend/src/, backend/tests/ or frontend/src/
#   - the tests for the changed part pass: backend ruff + unit + API tests, frontend tests
# verdict.json: {decision: "pr" | "none", reason, changed: [...], tests: [{name, command, passed}]}
#
# Env: RESPONDER_BACKEND_TESTS, RESPONDER_FRONTEND_TESTS (override the test commands; the tests of
# this script use them).
set -uo pipefail

out="${1:-}"
if [[ -z "$out" ]]; then
  echo "usage: $0 <out-dir>" >&2
  exit 2
fi
backend_tests="${RESPONDER_BACKEND_TESTS:-cd backend && uv sync --locked --quiet && uv run ruff check . && uv run pytest -q tests/unit tests/api}"
frontend_tests="${RESPONDER_FRONTEND_TESTS:-cd frontend && npm ci --no-audit --no-fund --silent && npm test}"
allowed='^(backend/src/|backend/tests/|frontend/src/)'

category="$(jq -r '.category // "unknown"' "$out/result.json" 2>/dev/null || echo unknown)"
# Only an explicit `false` counts: missing facts don't block a fix.
reachable="$(jq -r 'if .reachable == false then "false" else "true" end' "$out/facts.json" 2>/dev/null || echo true)"

git add -A
changed="$(git diff --cached --name-only)"
git diff --cached --binary >"$out/patch.diff"
: >"$out/tests.log"

tests_json='[]'
decision="none"
reason=""
outside="$(grep -Ev "$allowed" <<<"$changed" | grep -v '^$' || true)"

if [[ "$category" != "code" ]]; then
  reason="the diagnosis is \`$category\`, not a code problem"
  [[ -n "$changed" ]] && reason="$reason; the model's file changes were discarded"
elif [[ "$reachable" != "true" ]]; then
  reason="the app did not answer at all, which a code change can't be checked against"
elif [[ -z "$changed" ]]; then
  reason="the model changed no files"
elif [[ -n "$outside" ]]; then
  reason="the model changed files outside backend/src, backend/tests and frontend/src: $(tr '\n' ' ' <<<"$outside")"
else
  all_passed=true
  run_tests() {
    local name="$1" command="$2" passed=true
    echo "\$ $command" >>"$out/tests.log"
    if ! (bash -c "$command") >>"$out/tests.log" 2>&1; then
      passed=false
      all_passed=false
    fi
    tests_json="$(jq -c --arg n "$name" --arg c "$command" --argjson p "$passed" \
      '. + [{name: $n, command: $c, passed: $p}]' <<<"$tests_json")"
  }
  if grep -q '^backend/' <<<"$changed"; then run_tests backend "$backend_tests"; fi
  if grep -q '^frontend/' <<<"$changed"; then run_tests frontend "$frontend_tests"; fi
  if [[ "$all_passed" == true ]]; then
    decision="pr"
    reason="the change is limited to the allowed paths and its tests pass"
  else
    reason="the model's change failed its tests"
  fi
fi

jq -n --arg d "$decision" --arg r "$reason" --arg changed "$changed" --argjson tests "$tests_json" \
  '{decision: $d, reason: $r, changed: ($changed | split("\n") | map(select(length > 0))), tests: $tests}' \
  >"$out/verdict.json"
echo "verdict: $decision ($reason)"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "decision=$decision" >>"$GITHUB_OUTPUT"
fi
