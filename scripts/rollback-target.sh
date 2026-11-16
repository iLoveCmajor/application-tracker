#!/usr/bin/env bash
# Pick the commit the Rollback workflow (#27) deploys, and print its full SHA on stdout.
#
#   scripts/rollback-target.sh [sha]
#
# With a SHA (full or abbreviated), resolve it to the full SHA of a commit on main. Without one, ask
# the live ${APP_URL}/health which commit it runs and take its parent (<live>^). Either way the
# target must be a commit on main (origin/main, or MAIN_REF); anything else is an ::error:: and
# exit 1, before any deploy. Needs the full history (actions/checkout with fetch-depth: 0).
#
# Env: APP_URL (only without a SHA), MAIN_REF (default origin/main), HEALTH_WAIT (seconds to keep
# retrying a sleeping instance's /health, default 240).
set -euo pipefail

input="${1:-}"
main_ref="${MAIN_REF:-origin/main}"

fail() {
  echo "::error::$1" >&2
  exit 1
}

# Full SHA of a commit given as a hex SHA (4 to 40 characters), or empty if git doesn't know it.
resolve() {
  [[ "$1" =~ ^[0-9a-fA-F]{4,40}$ ]] || return 0
  git rev-parse --verify --quiet "$1^{commit}" || true
}

on_main() {
  git merge-base --is-ancestor "$1" "$main_ref"
}

git rev-parse --verify --quiet "$main_ref^{commit}" >/dev/null || fail "$main_ref is not available; check out the full history"

if [[ -n "$input" ]]; then
  target="$(resolve "$input")"
  [[ -n "$target" ]] || fail "'$input' is not a known commit SHA"
  on_main "$target" || fail "$target is not a commit on main"
  echo "requested: $input" >&2
else
  : "${APP_URL:?APP_URL is not set}"
  url="${APP_URL%/}/health"
  deadline=$(($(date +%s) + ${HEALTH_WAIT:-240}))
  # A free instance sleeps when idle; retry until it answers.
  while :; do
    live_version=$(curl -sS --max-time 60 "$url" | jq -r '.version // empty' 2>/dev/null || true)
    [[ -n "$live_version" ]] && break
    [[ "$(date +%s)" -lt "$deadline" ]] || fail "$url did not report a version"
    echo "$url not answering yet, retrying" >&2
    sleep 10
  done
  live="$(resolve "$live_version")"
  [[ -n "$live" ]] || fail "$url reports version '$live_version', which is not a known commit"
  on_main "$live" || fail "the live commit $live is not on main"
  target="$(git rev-parse --verify --quiet "$live^1^{commit}" || true)"
  [[ -n "$target" ]] || fail "the live commit $live has no parent to roll back to"
  echo "live:   $live" >&2
fi

echo "target: $target $(git log -1 --format=%s "$target")" >&2
echo "$target"
