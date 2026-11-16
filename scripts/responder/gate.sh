#!/usr/bin/env bash
# First step of the responder workflow (#26): decides whether this run goes ahead.
#
#   scripts/responder/gate.sh 42
#
# Goes ahead (`run=true` in $GITHUB_OUTPUT, exit 0) only when the ANTHROPIC_API_KEY secret is set
# and issue 42 is open and labelled `alert`. Otherwise it ends the run green with a notice:
# nothing is posted and nothing is opened.
#
# Inputs are checked before anything is written to $GITHUB_OUTPUT: the issue number must be digits
# only, and INPUT_URL (the dispatch's `url`, when given) must be one line starting with http:// or
# https://. A bad one ends the run green with a notice; `issue=` is written only for a valid number.
#
# Env: INPUT_URL, HAS_KEY ("true" when the secret is set; the workflow never passes the key itself here),
# ALLOW_UNLABELLED ("true" for a manual dispatch: someone with write access asked for this issue,
# as in the code-fault demo), GH_TOKEN and GH_REPO (or a checkout gh can read the repo from).
set -euo pipefail

issue="${1:-}"
go() {
  echo "run=$1" >>"${GITHUB_OUTPUT:-/dev/null}"
  echo "run=$1"
}

# $issue may hold anything, even newlines: nothing of it is echoed until it is known to be digits.
if [[ ! "$issue" =~ ^[0-9]+$ ]]; then
  echo "::notice title=Responder skipped::The issue input is not an issue number."
  go false
  exit 0
fi
echo "issue=$issue" >>"${GITHUB_OUTPUT:-/dev/null}"
input_url="${INPUT_URL-}"
if [[ -n "$input_url" ]] && { [[ ! "$input_url" =~ ^https?://[^[:space:]]+$ ]] || [[ "$input_url" == *$'\n'* ]]; }; then
  echo "::notice title=Responder skipped::The url input must be one line starting with http:// or https://."
  go false
  exit 0
fi
if [[ "${HAS_KEY:-}" != "true" ]]; then
  echo "::notice title=Responder skipped::The ANTHROPIC_API_KEY secret is not set, so the responder did not run for #$issue (README, \"On-call responder\")."
  go false
  exit 0
fi
info="$(gh issue view "$issue" --json state,labels \
  --jq '[.state, ([.labels[].name] | index("alert") != null)] | @tsv')"
read -r state labelled <<<"$info"
if [[ "$state" != "OPEN" ]]; then
  echo "::notice title=Responder skipped::#$issue is not an open issue."
  go false
  exit 0
fi
if [[ "$labelled" != "true" && "${ALLOW_UNLABELLED:-}" != "true" ]]; then
  echo "::notice title=Responder skipped::#$issue is not labelled alert."
  go false
  exit 0
fi
go true
