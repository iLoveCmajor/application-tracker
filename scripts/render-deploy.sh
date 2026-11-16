#!/usr/bin/env bash
# Deploy one commit to Render and wait until the live /health reports it. Used by the CI `deploy-dev` and
# `deploy-prod` jobs (#11, #28) and the Rollback workflow (#27).
#
#   DEPLOY_HOOK_URL=… APP_URL=https://… scripts/render-deploy.sh <full commit sha>
#
# The hook URL is a secret and already carries ?key=…; it is never printed. `ref=<sha>` pins the
# deploy to that commit. Free instances sleep and a Docker build takes a few minutes, so /health is
# polled for up to DEPLOY_WAIT seconds (default 600). Exit 0 once /health reports the commit.
set -euo pipefail

sha="${1:-}"
if [[ -z "$sha" ]]; then
  echo "usage: $0 <commit sha>" >&2
  exit 2
fi
: "${DEPLOY_HOOK_URL:?DEPLOY_HOOK_URL is not set}"
: "${APP_URL:?APP_URL is not set}"
wait_s="${DEPLOY_WAIT:-600}"
interval="${DEPLOY_INTERVAL:-15}"
response="$(mktemp)"
trap 'rm -f "$response"' EXIT

# Trigger the deploy hook.
case "$DEPLOY_HOOK_URL" in *\?*) sep='&' ;; *) sep='?' ;; esac
code=$(curl -sS -X POST -o "$response" -w '%{http_code}' "${DEPLOY_HOOK_URL}${sep}ref=${sha}") || true
echo "Render answered HTTP $code: $(cat "$response")"
case "$code" in
  200 | 202) ;;
  *)
    echo "::error::The deploy hook returned HTTP $code"
    exit 1
    ;;
esac

# Wait until /health reports this commit.
url="${APP_URL%/}/health"
deadline=$(($(date +%s) + wait_s))
while :; do
  version=$(curl -sS --max-time 60 "$url" | jq -r '.version // empty' 2>/dev/null || true)
  if [[ "$version" == "$sha" ]]; then
    echo "$url reports version $version"
    exit 0
  fi
  if [[ "$(date +%s)" -ge "$deadline" ]]; then
    echo "::error::$url still reports version '${version:-unreachable}', expected $sha after $wait_s seconds"
    exit 1
  fi
  echo "version '${version:-unreachable}', waiting for $sha"
  sleep "$interval"
done
