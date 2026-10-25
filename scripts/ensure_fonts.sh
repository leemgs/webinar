#!/usr/bin/env bash
# Chromium's renderer aborts on any page with a web font when fontconfig finds
# no fonts at all (FATAL remote_font_face_source.cc "NOTREACHED hit" → "Page
# crashed") — e.g. a minimal Ubuntu server used as the self-hosted runner.
# Without sudo, unpack a Korean + a Latin font package into a user dir (once;
# cached) and write a fontconfig file that adds it to the system fonts.
#
# usage: scripts/ensure_fonts.sh   → prints the fonts.conf path for FONTCONFIG_FILE
set -euo pipefail
dir="$HOME/.cache/webinar-fonts"
conf="$dir/fonts.conf"
mkdir -p "$dir/fonts"

has_fonts() { find "$dir/fonts" -type f -size +10k \( -name '*.ttf' -o -name '*.otf' -o -name '*.ttc' \) | grep -q .; }

if ! has_fonts; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  # the machine's own Ubuntu mirror; apt-get download needs no root
  for pkg in fonts-nanum fonts-dejavu-core; do
    (cd "$tmp" && apt-get download "$pkg" >/dev/null 2>&1) || echo "apt-get download $pkg failed" >&2
  done
  for deb in "$tmp"/*.deb; do
    [ -e "$deb" ] && { dpkg-deb -x "$deb" "$tmp/x" || echo "could not unpack $deb" >&2; }
  done
  [ -d "$tmp/x" ] && find "$tmp/x" -type f \( -name '*.ttf' -o -name '*.otf' \) -exec cp {} "$dir/fonts/" \;
  if ! has_fonts; then
    curl -fsSL -o "$dir/fonts/NanumGothic-Regular.ttf" \
      "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf" \
      || echo "font download failed" >&2
  fi
fi

if ! has_fonts; then
  echo "::warning::no fonts for Chromium — pages will crash. Install once: sudo apt-get install -y fonts-nanum fonts-dejavu-core" >&2
fi

cat > "$conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>$dir/fonts</dir>
  <cachedir>$dir/cache</cachedir>
</fontconfig>
EOF
echo "$conf"
