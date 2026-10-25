#!/usr/bin/env bash
# Print the runner facts that decide whether Chromium can render pages — memory,
# /dev/shm, display and limits — so a run where every site returns 0 can be
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
# Chromium A/B: the inherited open-files limit vs. the capped one the scrape
# uses (scripts/with_display.sh). Browser stderr lines explain a crash.
here="$(dirname "$0")"
for cap in 0 65536; do
  echo "--- Chromium probe (WEBINAR_MAX_NOFILE=$cap; 0 = inherited limit)"
  WEBINAR_MAX_NOFILE=$cap DEBUG=pw:browser timeout 180 "$here/with_display.sh" python "$here/chromium_probe.py" 2>&1 \
    | grep -E "^(open files|OK|CRASH|FAIL)|FATAL|Check failed|ERROR:|Received signal|Trace/breakpoint" \
    | grep -vE "bus\.cc|dbus" \
    | awk '{ k = $0; sub(/.*\] /, "", k); if (!(k in seen)) { seen[k] = 1; print; fflush() } }' \
    | head -30 || true
done
exit 0
