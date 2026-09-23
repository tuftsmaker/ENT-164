#!/usr/bin/env bash
# Regenerate the syllabus PDF from syllabus/index.html, or verify that the
# committed PDF matches its source (the check CI runs).
#
# The syllabus PDF is a generated artifact. Never edit or replace it by hand:
# the web page is the single source of truth, exactly like the class decks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAGE_DIR="$ROOT/syllabus"
PDF_NAME="ENT-164-Syllabus-Fall-2026.pdf"
PAGE="$PAGE_DIR/index.html"

usage() {
  cat <<'EOF'
Usage:
  scripts/build-syllabus.sh           regenerate the syllabus PDF
  scripts/build-syllabus.sh --check   verify the committed PDF is current

The PDF is written next to syllabus/index.html, and syllabus.buildinfo records
the source hash so CI can detect drift (see .github/workflows/slides-sync.yml).

Environment:
  CHROME_BIN    Chrome/Chromium binary (autodetected when omitted)
  CHROME_FLAGS  extra flags for the headless print command
EOF
}

find_chrome() {
  if [[ -n "${CHROME_BIN:-}" && -x "${CHROME_BIN}" ]]; then
    printf '%s\n' "$CHROME_BIN"
    return 0
  fi
  local candidates=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "$(command -v google-chrome 2>/dev/null || true)"
    "$(command -v google-chrome-stable 2>/dev/null || true)"
    "$(command -v chromium 2>/dev/null || true)"
    "$(command -v chromium-browser 2>/dev/null || true)"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -n "$c" && -x "$c" ]]; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  echo "ERROR: no Chrome/Chromium found; set CHROME_BIN" >&2
  return 1
}

if [[ "${1:-}" == "--check" ]]; then
  exec python3 "$ROOT/scripts/pdf_buildinfo.py" check syllabus
fi

if [[ $# -gt 0 ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "$PAGE" ]]; then
  echo "ERROR: $PAGE not found" >&2
  exit 1
fi

chrome="$(find_chrome)"
"$chrome" --headless=new --disable-gpu --no-pdf-header-footer \
  ${CHROME_FLAGS:-} --virtual-time-budget=12000 \
  --print-to-pdf="$PAGE_DIR/$PDF_NAME" "file://$PAGE" >/dev/null 2>&1 || true

if [[ ! -s "$PAGE_DIR/$PDF_NAME" ]]; then
  echo "ERROR: $PAGE_DIR/$PDF_NAME was not produced" >&2
  exit 1
fi

python3 "$ROOT/scripts/pdf_buildinfo.py" write "$PAGE_DIR" "$PDF_NAME"
