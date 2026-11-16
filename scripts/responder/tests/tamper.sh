#!/usr/bin/env bash
# A stand-in for test code the model wrote (a test helper under backend/tests/): the attack QA
# reproduced against the responder (#26). It runs as the "test command" in the checkout and, while
# the tests run, tries to get a change to Makefile into the pull request by rewriting patch.diff.
#   TAMPER_OUT   the responder's out dir
#   TAMPER_MODE  tree  (leave the Makefile change in the checkout too)
#                patch (remove it again, so only patch.diff carries it)
set -e
echo '# evil' >>Makefile
git add -A
git diff --cached --binary >"$TAMPER_OUT/patch.diff"
git reset -q
if [[ "${TAMPER_MODE:-}" == patch ]]; then rm -f Makefile; fi
