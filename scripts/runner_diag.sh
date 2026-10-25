#!/usr/bin/env bash
# Print the runner facts that decide whether Chromium can render pages — memory,
# /dev/shm, fonts, display and limits — so a run where every site returns 0 can be
# traced to the machine rather than the sites. Never fails the job.
set -u
echo "host: $(uname -srm) | $( (. /etc/os-release && echo "$PRETTY_NAME") 2>/dev/null) | virt: $(systemd-detect-virt 2>/dev/null || echo unknown) | cpus: $(nproc 2>/dev/null)"
free -m 2>/dev/null || true
df -h /dev/shm /tmp 2>/dev/null || true
echo "DISPLAY=${DISPLAY:-<unset>} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<unset>} xvfb-run=$(command -v xvfb-run || echo missing)"
echo "open files: $(ulimit -n) | processes: $(ulimit -u) | virtual memory: $(ulimit -v)"
if [ -r /sys/fs/cgroup/memory.max ]; then
  echo "cgroup memory.max: $(cat /sys/fs/cgroup/memory.max)"
fi
avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
if [ "${avail_mb:-0}" -gt 0 ] && [ "$avail_mb" -lt 1500 ]; then
  echo "::warning::runner has only ${avail_mb} MB memory available — Chromium pages may crash (needs ~1.5 GB+)"
fi
echo "fonts: $(fc-list 2>/dev/null | wc -l) (FONTCONFIG_FILE=${FONTCONFIG_FILE:-<unset>}) | sans-serif → $(fc-match sans-serif 2>/dev/null || echo '?')"
# open two listings in Chromium; the browser's own error lines explain a crash
here="$(dirname "$0")"
echo "--- Chromium probe"
DEBUG=pw:browser timeout 180 "$here/with_display.sh" python "$here/chromium_probe.py" 2>&1 \
  | grep -aE "^(open files|OK|CRASH|FAIL)|FATAL|Check failed|any font|Received signal" \
  | awk '{ k = $0; sub(/.*\] /, "", k); if (!(k in seen)) { seen[k] = 1; print; fflush() } }' \
  | head -30 || true
exit 0
