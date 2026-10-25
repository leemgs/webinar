#!/usr/bin/env bash
# Commit the generated dataset (+ manual entries) and push to main, surviving
# concurrent writers (the daily sync and the manual-entry workflow can both
# push data).
#
# usage: scripts/commit_data.sh "<commit message>" [rebuild command ...]
#
# If the push is rejected because main moved, reset to the latest origin/main,
# run the rebuild command — which must re-apply THIS run's results on top
# (e.g. `python -m webinar.pipeline --merge-from scraped.json`) — and retry.
set -euo pipefail

msg="$1"; shift
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
files=(data/webinars.json docs/webinars.json docs/webinars.ics config/manual_webinars.yaml)

for attempt in 1 2 3 4; do
  git add -- "${files[@]}"
  if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
  fi
  git commit -q -m "$msg"
  if git push origin HEAD:main; then
    exit 0
  fi
  echo "push rejected (attempt ${attempt}); rebuilding on the latest main"
  git fetch -q origin main
  git reset -q --hard origin/main
  if [ "$#" -gt 0 ]; then
    "$@"
  fi
  sleep $((attempt * 3))
done
echo "giving up: could not push after 4 attempts" >&2
exit 1
