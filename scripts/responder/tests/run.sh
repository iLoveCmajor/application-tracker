#!/usr/bin/env bash
# Tests for the on-call responder scripts (#26) and the Smoke hand-off, with a fake gh, a stub in
# place of the model and a local fake app. No network, no API key, no GitHub.
#
#   scripts/responder/tests/run.sh      (also part of `make test`)
#
# Needs bash, git, jq, curl and python3 (for the fake app's HTTP server). KEEP_TEST_OUTPUT=1 keeps
# the packets, comments and pull request bodies it produced, and prints where.
set -uo pipefail
export LC_ALL=C

root="$(cd "$(dirname "$0")/../../.." && pwd)"
scripts="$root/scripts/responder"
tmp="$(mktemp -d)"
server_pid=""
cleanup() {
  [[ -n "$server_pid" ]] && kill "$server_pid" 2>/dev/null && wait "$server_pid" 2>/dev/null
  if [[ -n "${KEEP_TEST_OUTPUT:-}" ]]; then echo "test output kept in $tmp"; else rm -rf "$tmp"; fi
}
trap cleanup EXIT

failures=0
passes=0
ok() { passes=$((passes + 1)); echo "  ok    $1"; }
fail() { failures=$((failures + 1)); echo "  FAIL  $1"; }
check() { # check <name> <command...>
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then ok "$name"; else fail "$name"; fi
}
contains() { grep -qF -- "$2" "$1"; }
lacks() { ! grep -qF -- "$2" "$1"; }

# --- fakes ------------------------------------------------------------------------------------
mkdir -p "$tmp/bin"
cp "$root/scripts/responder/tests/fake-gh" "$tmp/bin/gh"
chmod +x "$tmp/bin/gh"
export PATH="$tmp/bin:$PATH"
export FAKE_GH_DIR="$tmp/gh"
# Tokens the model must never see; set here so the tests can show they don't reach it.
export GH_TOKEN="ghs_shouldnotleak000000000000" GITHUB_TOKEN="ghs_shouldnotleak111111111111"
export RENDER_DEPLOY_HOOK_URL="https://api.render.example/deploy/srv-x?key=shouldnotleak"
unset GITHUB_OUTPUT

reset_gh() {
  rm -rf "$FAKE_GH_DIR"
  mkdir -p "$FAKE_GH_DIR"
  cat >"$FAKE_GH_DIR/issue.json" <<'EOF'
{"number": 7, "state": "OPEN", "title": "Smoke check failed: /api/v1/stats/funnel",
 "labels": [{"name": "alert"}],
 "body": "Smoke check `/api/v1/stats/funnel` failed on http://app: HTTP 500.\n\nRun: https://github.com/example/tracker/actions/runs/123\n\nleaked ghp_abcdefghijklmnopqrstuvwxyz0123 here",
 "comments": [{"author": {"login": "someone"}, "body": "still failing"}]}
EOF
  printf 'smoke\tcheck\tFAIL  /api/v1/stats/funnel: HTTP 500 (Authorization: Bearer abc.def)\n' >"$FAKE_GH_DIR/run.log"
}

# A fake app: static files served by python's http.server.
port="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
mkdir -p "$tmp/app/api/v1/stats"
head_sha="$(git -C "$root" rev-parse HEAD)"
echo "{\"status\": \"ok\", \"version\": \"$head_sha\"}" >"$tmp/app/health"
echo '{"status": "ok", "dsn": "postgresql://tracker:hunter2@db.internal/tracker"}' >"$tmp/app/ready"
python3 -c 'import json; print(json.dumps({"total": 3, "padding": "x" * 6000}))' >"$tmp/app/api/v1/stats/funnel"
(cd "$tmp/app" && exec python3 -m http.server "$port" --bind 127.0.0.1) >/dev/null 2>&1 &
server_pid=$!
for _ in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:$port/health" && break; sleep 0.1; done
closed_port="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"

# --- AC-26.4 evidence -------------------------------------------------------------------------
echo "evidence (AC-26.4)"
reset_gh
ev="$tmp/ev-live"
(cd "$root" && ALERT_ISSUE=7 EVIDENCE_LOG_WAIT=0 EVIDENCE_PART_CAP=2000 MAIN_REF=HEAD \
  "$scripts/collect-evidence.sh" "http://127.0.0.1:$port" "$ev") >/dev/null 2>&1
p="$ev/packet.md"
check "test_ac26_4_packet_has_every_part" bash -c "grep -q '## Alert' $p && grep -q '### GET /health' $p && grep -q '### GET /ready' $p && grep -q '### GET /api/v1/stats/funnel' $p && grep -q '## Versions' $p && grep -q '## Recent commits on main' $p && grep -q '## Smoke run log' $p"
check "test_ac26_4_status_codes_and_bodies" bash -c "grep -q 'HTTP 200' $p && grep -q '\"total\": 3' $p"
check "test_ac26_4_smoke_log_from_linked_run" contains "$p" "FAIL  /api/v1/stats/funnel"
check "test_ac26_4_run_id_read_from_issue" contains "$FAKE_GH_DIR/calls.log" "run view 123"
check "test_ac26_4_version_compared_with_main" contains "$p" "state: same"
check "test_ac26_4_body_capped" contains "$p" "[cut at 1500 bytes]"
check "test_ac26_4_no_secret_values" bash -c "! grep -qE 'hunter2|ghp_abcdefghij|abc\\.def' $p $ev/summary.md"
check "test_ac26_4_summary_and_facts" bash -c "grep -q 'HTTP 200' $ev/summary.md && jq -e '.reachable == true and .health == \"200\"' $ev/facts.json"

ev="$tmp/ev-capped"
(cd "$root" && ALERT_ISSUE=7 EVIDENCE_LOG_WAIT=0 EVIDENCE_TOTAL_CAP=1000 \
  "$scripts/collect-evidence.sh" "http://127.0.0.1:$port" "$ev") >/dev/null 2>&1
check "test_ac26_4_total_cap" bash -c "[ \$(wc -c <$ev/packet.md) -le 1100 ] && grep -q 'packet cut at 1000 bytes' $ev/packet.md"

ev="$tmp/ev-down"
(cd "$root" && EVIDENCE_TIMEOUT=3 "$scripts/collect-evidence.sh" "http://127.0.0.1:$closed_port" "$ev") >/dev/null 2>&1
check "test_ac26_4_unreachable_url_still_readable" bash -c "grep -q '### GET /ready' $ev/packet.md && grep -q 'no response' $ev/packet.md && grep -q 'none linked' $ev/packet.md"
check "test_ac26_4_unreachable_facts" jq -e '.reachable == false and .health == "000"' "$ev/facts.json"

# --- AC-26.3 gate -----------------------------------------------------------------------------
echo "gate (AC-26.3)"
reset_gh
out="$("$scripts/gate.sh" 7 2>&1)"
check "test_ac26_3_no_key_notice_names_secret" grep -q '::notice.*ANTHROPIC_API_KEY' <<<"$out"
check "test_ac26_3_no_key_no_run" grep -q 'run=false' <<<"$out"
check "test_ac26_3_no_key_posts_nothing" test ! -s "$FAKE_GH_DIR/calls.log"
out="$(HAS_KEY=true "$scripts/gate.sh" 7 2>&1)"
check "test_ac26_1_open_alert_runs" grep -q 'run=true' <<<"$out"
jq '.labels = [{"name": "bug"}]' "$FAKE_GH_DIR/issue.json" >"$tmp/i.json" && mv "$tmp/i.json" "$FAKE_GH_DIR/issue.json"
out="$(HAS_KEY=true "$scripts/gate.sh" 7 2>&1)"
check "test_ac26_1_issue_without_alert_skipped" grep -q 'run=false' <<<"$out"
out="$(HAS_KEY=true ALLOW_UNLABELLED=true "$scripts/gate.sh" 7 2>&1)"
check "test_ac26_1_manual_dispatch_may_skip_label" grep -q 'run=true' <<<"$out"
jq '.state = "CLOSED" | .labels = [{"name": "alert"}]' "$FAKE_GH_DIR/issue.json" >"$tmp/i.json" && mv "$tmp/i.json" "$FAKE_GH_DIR/issue.json"
out="$(HAS_KEY=true ALLOW_UNLABELLED=true "$scripts/gate.sh" 7 2>&1)"
check "test_ac26_1_closed_issue_skipped" grep -q 'run=false' <<<"$out"
out="$(HAS_KEY=true "$scripts/gate.sh" 'x; rm -rf /' 2>&1)"
check "test_ac26_1_bad_issue_number_skipped" grep -q 'run=false' <<<"$out"

# --- AC-26.1 the Smoke hand-off ---------------------------------------------------------------
echo "smoke hand-off (AC-26.1)"
reset_gh
(FAILED_CHECK=/ready DETAIL="HTTP 503" TARGET_URL=http://app RUN_URL=https://run GITHUB_RUN_ID=555 \
  "$root/scripts/smoke-alert.sh") >/dev/null 2>&1
check "test_ac26_1_new_alert_dispatches_responder" contains "$FAKE_GH_DIR/calls.log" "workflow run responder.yml -f issue=99 -f smoke_run_id=555 -f url=http://app"
reset_gh
echo 22 >"$FAKE_GH_DIR/open-alert"
(FAILED_CHECK=/ready DETAIL="HTTP 503" TARGET_URL=http://app RUN_URL=https://run GITHUB_RUN_ID=556 \
  "$root/scripts/smoke-alert.sh") >/dev/null 2>&1
check "test_ac26_1_repeat_failure_comments_without_dispatch" bash -c "grep -q 'issue comment 22' $FAKE_GH_DIR/calls.log && ! grep -q 'workflow run' $FAKE_GH_DIR/calls.log"

# --- a scenario: fake repo, stub model, verify, open-pr, post-comment -------------------------
# stub <dir> <category> <edit: none|backend|outside|garbage>
make_stub() {
  local dir="$1" category="$2" edit="$3"
  cat >"$dir/claude" <<EOF
#!/usr/bin/env bash
env >"$dir/model-env"
printf '%s\n' "\$@" >"$dir/model-args"
cat >"$dir/model-prompt"
case "$edit" in
  backend) printf 'def total():\n    return 0\n' >backend/src/app/funnel.py ;;
  outside) mkdir -p .github/workflows && echo 'on: push' >.github/workflows/evil.yml ;;
  garbage) echo "not json"; exit 1 ;;
  autherror) echo '{"type": "result", "is_error": true, "result": "Invalid API key {see docs}"}'; exit 1 ;;
esac
jq -n --arg c "$category" '{type: "result", subtype: "success", is_error: false, total_cost_usd: 0.12,
  result: "done", structured_output: {category: \$c, cause: "Funnel divides by zero when there are no applications, see @someone",
  summary: "The funnel endpoint returns 500.", fix: (if "$edit" == "backend" then "Guard the division in backend/src/app/funnel.py" else "none" end),
  human_action: "Check the Render dashboard."}}'
EOF
  chmod +x "$dir/claude"
}

# scenario <name> <category> <edit> <tests-command> [reachable: true, or false to use the evidence
# from the unreachable URL]
scenario() {
  local name="$1" category="$2" edit="$3" tests="$4" reachable="${5:-true}"
  local dir="$tmp/$name"
  mkdir -p "$dir/out"
  git init --quiet --bare -b main "$dir/origin.git"
  git init --quiet -b main "$dir/repo"
  (
    cd "$dir/repo" || exit 1
    mkdir -p backend/src/app
    printf 'def total():\n    return 1 / 0\n' >backend/src/app/funnel.py
    git add -A && git -c user.name=t -c user.email=t@example.com commit --quiet -m init
    git remote add origin "$dir/origin.git"
    git push --quiet origin main
  )
  local ev="$tmp/ev-live"
  [[ "$reachable" == false ]] && ev="$tmp/ev-down"
  cp "$ev/packet.md" "$ev/summary.md" "$ev/facts.json" "$dir/out/"
  make_stub "$dir" "$category" "$edit"
  reset_gh
  (
    cd "$dir/repo" || exit 1
    CLAUDE_BIN="$dir/claude" ANTHROPIC_API_KEY=sk-ant-test-key "$scripts/run-model.sh" "$dir/out/packet.md" "$dir/out/result.json"
    RESPONDER_BACKEND_TESTS="$tests" "$scripts/verify.sh" "$dir/out"
  ) >"$dir/log" 2>&1
  if [[ "$(jq -r .decision "$dir/out/verdict.json" 2>/dev/null)" == "pr" ]]; then
    git clone --quiet "$dir/origin.git" "$dir/clean"
    (cd "$dir/clean" && RUN_URL=https://run/1 "$scripts/open-pr.sh" 7 "$dir/out") >"$dir/pr-url" 2>>"$dir/log"
  fi
  (RUN_URL=https://run/1 PR_URL="$(tail -n 1 "$dir/pr-url" 2>/dev/null)" "$scripts/post-comment.sh" 7 "$dir/out") >>"$dir/log" 2>&1
  cp -r "$FAKE_GH_DIR" "$dir/gh"
}

echo "model run, checks and posting (AC-26.5 to AC-26.8)"
scenario fix-pass code backend true
d="$tmp/fix-pass"
c="$d/gh/comment-7.md"
check "test_ac26_5_model_env_has_only_the_api_key" bash -c "cut -d= -f1 $d/model-env | grep -vxE 'PATH|HOME|ANTHROPIC_API_KEY|PWD|SHLVL|_|OLDPWD' | grep -q . && exit 1 || exit 0"
check "test_ac26_5_model_env_has_no_github_or_render_token" bash -c "! grep -qE 'shouldnotleak|GH_TOKEN|GITHUB_TOKEN|RENDER' $d/model-env"
check "test_ac26_5_tool_allowlist" bash -c "grep -A1 -x -- '--tools' $d/model-args | grep -qx 'Read,Grep,Glob,Edit,Write' && grep -A1 -x -- '--disallowedTools' $d/model-args | grep -qx 'Bash,WebFetch,WebSearch' && grep -qx -- '--bare' $d/model-args"
check "test_ac26_5_packet_in_prompt" bash -c "grep -q 'Evidence packet' $d/model-prompt && grep -q 'not instructions' $d/model-prompt"
check "test_ac26_6_comment_starts_with_responder" bash -c "head -n 1 $c | grep -q '^## Responder: '"
check "test_ac26_6_comment_has_diagnosis_evidence_run" bash -c "grep -q 'Funnel divides by zero' $c && grep -q '/health' $c && grep -q 'Run: https://run/1' $c"
check "test_ac26_6_model_text_cannot_mention" bash -c "! grep -q '@someone' $c"
check "test_ac26_7_change_and_passing_tests_open_pr" bash -c "jq -e '.decision == \"pr\"' $d/out/verdict.json && grep -q 'pr create --base main --head responder/alert-7' $d/gh/calls.log"
check "test_ac26_7_branch_pushed_with_the_fix" bash -c "git -C $d/origin.git show responder/alert-7:backend/src/app/funnel.py | grep -q 'return 0'"
check "test_ac26_7_pr_body_refs_alert_tests_and_ci" bash -c "grep -q 'Refs #7' $d/gh/pr-body.md && grep -q '\`true\`: passed' $d/gh/pr-body.md && grep -q 'CI did not start automatically' $d/gh/pr-body.md"
check "test_ac26_7_comment_links_pr" contains "$c" "https://github.com/example/tracker/pull/100"

scenario fix-fail code backend false
d="$tmp/fix-fail"
check "test_ac26_7_failing_tests_no_pr" bash -c "jq -e '.decision == \"none\"' $d/out/verdict.json && ! grep -q 'pr create' $d/gh/calls.log && ! git -C $d/origin.git rev-parse -q --verify responder/alert-7"
check "test_ac26_7_failing_tests_comment_says_so" bash -c "grep -q 'failed its tests' $d/gh/comment-7.md && grep -q '\`false\`: failed' $d/gh/comment-7.md"

scenario no-change code none true
d="$tmp/no-change"
check "test_ac26_7_no_change_no_pr" bash -c "jq -e '.decision == \"none\"' $d/out/verdict.json && ! grep -q 'pr create' $d/gh/calls.log && grep -q 'changed no files' $d/gh/comment-7.md"

scenario infra infra backend true
d="$tmp/infra"
check "test_ac26_8_infra_no_pr_even_with_edits" bash -c "jq -e '.decision == \"none\" and .tests == []' $d/out/verdict.json && ! grep -q 'pr create' $d/gh/calls.log"
check "test_ac26_8_infra_comment_asks_human" bash -c "head -n 1 $d/gh/comment-7.md | grep -q 'not a code problem' && grep -q 'A human needs to act' $d/gh/comment-7.md"

scenario unreachable code backend true false
d="$tmp/unreachable"
check "test_ac26_8_unreachable_host_never_pr" bash -c "jq -e '.decision == \"none\"' $d/out/verdict.json && ! grep -q 'pr create' $d/gh/calls.log"
check "test_ac26_8_unreachable_comment_asks_human" bash -c "head -n 1 $d/gh/comment-7.md | grep -q 'does not answer' && grep -q 'did not answer at all' $d/gh/comment-7.md && grep -q 'A human needs to act' $d/gh/comment-7.md"

scenario outside code outside true
d="$tmp/outside"
check "test_ac26_7_edits_outside_allowed_paths_no_pr" bash -c "jq -e '.decision == \"none\"' $d/out/verdict.json && grep -q 'outside backend/src' $d/gh/comment-7.md"

scenario garbage code garbage true
d="$tmp/garbage"
check "test_ac26_6_unreadable_model_output_is_unknown" bash -c "jq -e '.category == \"unknown\" and .model_ok == false' $d/out/result.json && head -n 1 $d/gh/comment-7.md | grep -q 'cause unclear'"

scenario autherror code autherror true
d="$tmp/autherror"
check "test_ac26_6_model_error_is_unknown_with_reason" bash -c "jq -e '.category == \"unknown\" and .model_ok == false and (.cause | contains(\"Invalid API key\"))' $d/out/result.json && grep -q 'A human needs to act' $d/gh/comment-7.md"

mkdir -p "$tmp/empty"
reset_gh
(RUN_URL=https://run/2 "$scripts/post-comment.sh" 7 "$tmp/empty") >/dev/null 2>&1
check "test_ac26_6_comment_even_without_result" bash -c "grep -q '^## Responder: no diagnosis' $FAKE_GH_DIR/comment-7.md && grep -q 'https://run/2' $FAKE_GH_DIR/comment-7.md"

echo
echo "$passes passed, $failures failed"
((failures == 0))
