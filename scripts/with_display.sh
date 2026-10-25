#!/usr/bin/env bash
# Run a command with a display so Chromium can run headed (WEBINAR_HEADED=1):
# an existing desktop session ($DISPLAY) is used as is; on a headless Linux box
# the command runs under Xvfb when xvfb-run is installed; otherwise it falls
# back to headless Chromium.
set -euo pipefail
if [ -n "${DISPLAY:-}" ] || [ "$(uname)" != "Linux" ]; then
  exec "$@"
elif command -v xvfb-run >/dev/null; then
  exec xvfb-run -a --server-args="-screen 0 1366x900x24" "$@"
else
  echo "no display and no xvfb-run: running Chromium headless" >&2
  WEBINAR_HEADED=0 exec "$@"
fi
