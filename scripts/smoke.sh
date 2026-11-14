#!/usr/bin/env bash
# Smoke check of a running deployment: /health, /ready and GET /api/v1/stats/funnel.
#
#   scripts/smoke.sh https://tracker.example.com
#
# A free-tier instance sleeps when idle and takes about a minute to wake, so every check retries
# until SMOKE_WAIT seconds (default 240) have passed since the start. Exit 0 when all pass, 1 when
# one fails. Under GitHub Actions the failing check and its last error go to $GITHUB_OUTPUT as
# `failed` and `detail`, which the alert step (scripts/smoke-alert.sh) uses.
#
# Env: SMOKE_WAIT (total seconds to keep retrying), SMOKE_INTERVAL (seconds between tries, default
# 10), SMOKE_TIMEOUT (seconds per request, default 60, long enough for a cold start).
set -uo pipefail

base="${1:-}"
if [[ -z "$base" ]]; then
  echo "usage: $0 <base-url>" >&2
  exit 2
fi
base="${base%/}"
wait_s="${SMOKE_WAIT:-240}"
interval="${SMOKE_INTERVAL:-10}"
timeout="${SMOKE_TIMEOUT:-60}"
deadline=$((SECONDS + wait_s))
body_file="$(mktemp)"
err_file="$(mktemp)"
trap 'rm -f "$body_file" "$err_file"' EXIT

# One try of a check: sets `detail` and returns non-zero on failure.
try_check() {
  local path="$1" expect="$2" code
  code="$(curl --silent --show-error --location --max-time "$timeout" \
    --header "X-Request-ID: smoke-${GITHUB_RUN_ID:-local}-${RANDOM}" \
    --output "$body_file" --write-out '%{http_code}' "$base$path" 2>"$err_file")"
  if [[ "$code" == "000" || -z "$code" ]]; then
    detail="no response ($(head -n 1 "$err_file"))"
    return 1
  fi
  if [[ "$code" != "200" ]]; then
    detail="HTTP $code"
    return 1
  fi
  if ! jq -e "$expect" "$body_file" >/dev/null 2>&1; then
    detail="HTTP 200 but unexpected body: $(head -c 200 "$body_file")"
    return 1
  fi
  return 0
}

run_check() {
  local path="$1" expect="$2" attempt=0
  while true; do
    attempt=$((attempt + 1))
    if try_check "$path" "$expect"; then
      echo "ok    $path (try $attempt)"
      return 0
    fi
    echo "retry $path (try $attempt): $detail"
    if ((SECONDS + interval >= deadline)); then
      return 1
    fi
    sleep "$interval"
  done
}

detail=""
for check in \
  '/health|.status == "ok"' \
  '/ready|.status == "ok"' \
  '/api/v1/stats/funnel|(.total | type) == "number"'; do
  path="${check%%|*}"
  expect="${check#*|}"
  if ! run_check "$path" "$expect"; then
    echo "FAIL  $path on $base: $detail"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      {
        echo "failed=$path"
        echo "detail=${detail//$'\n'/ }"
      } >>"$GITHUB_OUTPUT"
    fi
    exit 1
  fi
done
echo "all checks passed on $base"
