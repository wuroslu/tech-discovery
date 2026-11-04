#!/usr/bin/env bash
# Candidate-cache persistence must not block a validated editorial deployment
# when GitHub itself is temporarily failing. Never force or overwrite a ref.
set -euo pipefail

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add data/news.json data/source_status.json
if git diff --cached --quiet; then
  exit 0
fi
git commit -m 'Update feed cache and source status'

push_log="$(mktemp)"
trap 'rm -f "$push_log"' EXIT
if git push >"$push_log" 2>&1; then
  cat "$push_log"
  exit 0
fi
cat "$push_log"

# Do not hide access denials, branch conflicts, or unknown failures. Those still
# require investigation. Never try to overwrite remote history after a 5xx.
if grep -Eiq 'Internal Server Error|returned error: 50[0-4]|HTTP[^0-9]*50[0-4]' "$push_log"; then
  echo '::warning::GitHub returned a server error while saving the candidate cache; the save was not confirmed. No forced update was attempted. Deploying the already validated editorial content.'
  exit 0
fi
exit 1
