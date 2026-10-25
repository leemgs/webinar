#!/usr/bin/env bash
# Run a command with a display so Chromium can run headed (WEBINAR_HEADED=1):
# an existing desktop session ($DISPLAY) is used as is; on a headless Linux box
# the command runs under Xvfb when xvfb-run is installed; otherwise it falls
# back to headless Chromium.
#
# The open-files limit is capped at WEBINAR_MAX_NOFILE (default 65536; 0 keeps
# it): a runner service with a huge limit (systemd LimitNOFILE=1048576) is a
# suspect for Chromium renderer crashes, and Chromium needs far fewer files.
set -euo pipefail
max_nofile="${WEBINAR_MAX_NOFILE:-65536}"
cur_nofile="$(ulimit -n)"
if [ "$max_nofile" -gt 0 ] && { [ "$cur_nofile" = unlimited ] || [ "$cur_nofile" -gt "$max_nofile" ]; }; then
  ulimit -n "$max_nofile"
fi
if [ -n "${DISPLAY:-}" ] || [ "$(uname)" != "Linux" ]; then
  exec "$@"
elif command -v xvfb-run >/dev/null; then
  exec xvfb-run -a --server-args="-screen 0 1366x900x24" "$@"
else
  echo "no display and no xvfb-run: running Chromium headless" >&2
  WEBINAR_HEADED=0 exec "$@"
fi
