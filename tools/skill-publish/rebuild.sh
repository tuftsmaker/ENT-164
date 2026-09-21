#!/usr/bin/env bash
#
# Rebuild skills/index.json after editing anything under skills/.
#
#   ./tools/skill-publish/rebuild.sh
#
# Then commit and push — that IS the publish step, because the site is served
# straight from this repo by GitHub Pages. No upload, no server.
#
# Why this is needed: opencode only re-downloads a skill when its `version`
# changes, and the version is a hash of the skill's contents. Edit a file
# without rebuilding and the version stays put, so students keep the old copy.
# Rebuild and it changes by itself — you never bump a version by hand.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$(dirname "$HERE")")"
SKILLS="$REPO/skills"

if [ ! -d "$SKILLS" ]; then
  echo "error: no skills directory at $SKILLS" >&2
  exit 1
fi

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: $PY not found. Set PYTHON=/path/to/python3 and retry." >&2
  exit 1
fi

echo "==> rebuilding $SKILLS/index.json"
"$PY" "$HERE/build-index.py" --in-place --src "$SKILLS"

echo
echo "Next: git add skills && git commit && git push"
echo "Then verify the live copy before relying on it:"
echo "  curl -s https://tuftsmaker.github.io/ENT-164/skills/index.json"
