#!/usr/bin/env bash
# Regenerate a class deck PDF from its slides.html, or verify that the
# committed PDF matches its sources (used by CI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLASSES_DIR="$ROOT/classes"

usage() {
  cat <<'EOF'
Usage:
  scripts/build-class.sh class-01 [class-02 ...]   regenerate PDFs
  scripts/build-class.sh --all                     regenerate every class
  scripts/build-class.sh --check [class-01 ...]    verify PDFs are current

The PDF is written next to slides.html, and slides.buildinfo records the
source hash so CI can detect drift (see .github/workflows/slides-sync.yml).

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

dir_for() {
  local arg="$1"
  if [[ -d "$arg" ]]; then
    printf '%s\n' "${arg%/}"
  else
    printf '%s\n' "$CLASSES_DIR/$arg"
  fi
}

pdf_name_for() {
  local dir="$1" existing num
  if [[ -n "${PDF_NAME:-}" ]]; then
    printf '%s\n' "$PDF_NAME"
    return
  fi
  existing="$(cd "$dir" && ls ENT-164-Class-*.pdf 2>/dev/null | head -n 1 || true)"
  if [[ -n "$existing" ]]; then
    printf '%s\n' "$existing"
    return
  fi
  num="$(basename "$dir" | sed -E 's/^class-0*([0-9]+)$/\1/')"
  printf 'ENT-164-Class-%s-Slides.pdf\n' "$num"
}

all_classes() {
  local d
  for d in "$CLASSES_DIR"/*/; do
    [[ -f "$d/slides.html" ]] || continue
    printf '%s\n' "${d%/}"
  done
}

build_one() {
  local dir chrome pdf
  dir="$(dir_for "$1")"
  if [[ ! -f "$dir/slides.html" ]]; then
    echo "ERROR: $dir/slides.html not found" >&2
    return 1
  fi
  chrome="$(find_chrome)"
  pdf="$(pdf_name_for "$dir")"
  "$chrome" --headless=new --disable-gpu --no-pdf-header-footer \
    ${CHROME_FLAGS:-} --virtual-time-budget=12000 \
    --print-to-pdf="$dir/$pdf" "file://$dir/slides.html" >/dev/null 2>&1 || true
  if [[ ! -s "$dir/$pdf" ]]; then
    echo "ERROR: $dir/$pdf was not produced" >&2
    return 1
  fi
  python3 "$ROOT/scripts/pdf_buildinfo.py" write "$dir" "$pdf"
}

args=("$@")
if [[ ${#args[@]} -eq 0 ]]; then
  usage
  exit 1
fi

mode="build"
if [[ "${args[0]}" == "--check" ]]; then
  mode="check"
  args=("${args[@]:1}")
fi

if [[ "$mode" == "check" ]]; then
  if [[ ${#args[@]} -eq 0 || "${args[0]}" == "--all" ]]; then
    exec python3 "$ROOT/scripts/pdf_buildinfo.py" check --all
  fi
  exec python3 "$ROOT/scripts/pdf_buildinfo.py" check "${args[@]}"
fi

declare -a dirs=()
if [[ "${args[0]}" == "--all" ]]; then
  while IFS= read -r d; do dirs+=("$d"); done < <(all_classes)
else
  dirs=("${args[@]}")
fi

if [[ ${#dirs[@]} -eq 0 ]]; then
  echo "No class decks found under $CLASSES_DIR" >&2
  exit 1
fi

for d in "${dirs[@]}"; do
  build_one "$d"
done
