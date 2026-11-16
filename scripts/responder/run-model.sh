#!/usr/bin/env bash
# Runs the model on the evidence packet in the current checkout, headless, and writes a normalised
# result for the steps after it (#26).
#
#   scripts/responder/run-model.sh out/packet.md out/result.json
#
# The model is Claude Code (`claude -p`) with only file tools: Read, Grep, Glob, Edit, Write. No
# Bash, no web tools, no MCP servers, no settings or hooks from the checkout (--bare). Its process
# gets an empty environment except PATH, HOME and ANTHROPIC_API_KEY, so no GitHub token or deploy
# secret can reach it, whatever the calling step has.
#
# result.json always comes out valid: {category: code|infra|unknown, cause, summary, fix,
# human_action, model, model_ok, cost_usd}. A failed or unreadable model run gives
# category "unknown" with the reason, so the workflow still reports to a human.
#
# The key's value and credential-shaped strings are redacted from result.json.
#
# Env: ANTHROPIC_API_KEY, RESPONDER_MODEL (default claude-sonnet-5-5), RESPONDER_BUDGET_USD
# (default 3), CLAUDE_BIN (default claude; the tests put a stub here).
set -uo pipefail

packet="${1:-}"
result="${2:-}"
if [[ -z "$packet" || -z "$result" ]]; then
  echo "usage: $0 <packet.md> <result.json>" >&2
  exit 2
fi
here="$(cd "$(dirname "$0")" && pwd)"
model="${RESPONDER_MODEL:-claude-sonnet-5-5}"
budget="${RESPONDER_BUDGET_USD:-3}"
claude_bin="${CLAUDE_BIN:-claude}"
tools="Read,Grep,Glob,Edit,Write"
# --allowedTools Read is not scoped to the checkout, and /proc/self/environ holds the API key, so
# the places outside the checkout that matter are denied by rule (permission rules: // is an
# absolute path, ~ the home directory, a leading / the project root). The edit rules keep the
# model's hands off what runs after it. Rules are defence in depth: the key is redacted from
# result.json below, and verify.sh checks the changed files whatever the model was allowed to do.
denied="Bash,WebFetch,WebSearch"
# shellcheck disable=SC2088 # a literal ~ in a permission rule, not a path
for d in //proc //sys //dev //etc //root //run //var //tmp "~/.*"; do denied="$denied,Read($d/**)"; done
for d in "/.github/**" "/scripts/**" /Makefile; do denied="$denied,Edit($d),Write($d)"; done
raw="$(mktemp)"
err="$(mktemp)"
prompt="$(mktemp)"
trap 'rm -f "$raw" "$err" "$prompt"' EXIT

{
  cat "$here/task.md"
  echo
  echo "---"
  echo
  cat "$packet"
} >"$prompt"

env -i PATH="$PATH" HOME="${HOME:-/tmp}" ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  "$claude_bin" -p --bare \
  --model "$model" \
  --tools "$tools" \
  --allowedTools "$tools" \
  --disallowedTools "$denied" \
  --permission-mode acceptEdits \
  --strict-mcp-config \
  --no-session-persistence \
  --max-budget-usd "$budget" \
  --output-format json \
  --json-schema "$(cat "$here/result.schema.json")" \
  <"$prompt" >"$raw" 2>"$err"
status=$?

# The structured result, or failing that a JSON object inside the plain-text result.
parsed="$(jq -c '
  if .is_error == true then empty
  elif (.structured_output | type) == "object" then .structured_output
  else (.result // "" | tostring | capture("(?s)(?<j>\\{.*\\})").j | fromjson)
  end' "$raw" 2>/dev/null || true)"
cost="$(jq -r '.total_cost_usd // empty' "$raw" 2>/dev/null || true)"

if [[ -z "$parsed" ]]; then
  reason="the model run gave no readable result (exit $status): $(head -c 300 "$err" | tr '\n' ' ')$(jq -r '.result // empty' "$raw" 2>/dev/null | head -c 300)"
  parsed="$(jq -nc --arg r "$reason" '{category: "unknown", cause: $r, summary: "", fix: "none",
    human_action: "Read the evidence below and the run log; the responder could not diagnose this."}')"
  ok=false
else
  ok=true
fi

# Whatever the model printed is redacted before anything is posted: the API key's own value
# (a comment on a public issue is attacker-written text that reaches the model) and credential
# shapes. The key comes in through the environment, not the command line.
K="${ANTHROPIC_API_KEY:-}" jq --arg model "$model" --argjson ok "$ok" --arg cost "$cost" '
  def redact:
    (if ($ENV.K | length) >= 8 then split($ENV.K) | join("[redacted]") else . end)
    | gsub("sk-ant-[A-Za-z0-9_-]+"; "[redacted]")
    | gsub("gh[pousr]_[A-Za-z0-9]{20,}"; "[redacted]")
    | gsub("github_pat_[A-Za-z0-9_]{20,}"; "[redacted]");
  def text($n): (. // "" | tostring | redact | .[0:$n]);
  {
    category: (if ((.category // "") | IN("code", "infra", "unknown")) then .category else "unknown" end),
    cause: (.cause | text(600)),
    summary: (.summary | text(2000)),
    fix: (.fix | text(1000)),
    human_action: (.human_action | text(600)),
    model: $model,
    model_ok: $ok,
    cost_usd: $cost
  }' <<<"$parsed" >"$result"

echo "model: $model, exit $status, category $(jq -r .category "$result")"
