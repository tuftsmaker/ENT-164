#!/bin/zsh
# Record the takes for a video project through browser-control.
#
#   ./tools/video-build/record.sh <project> [take ...]
#
# For each take it runs, in order:
#   1. the take's SETUP script   (recorder stopped - lands the app in the right state)
#   2. the pre-flight            (forces a true 1920x1080 surface, hides the badge)
#   3. recording start
#   4. the take script           (timed actions + marks)
#   5. recording stop
#   6. a report: duration, capture surface, marks, and the content rectangle
#
# Recordings and intermediates stay in the project's workDir, never in the repo.
#
# Prerequisites:
#   - browser-control relay running and the Onshape tab attached
#   - `pipeline.py align` already run (the scenes read the sentence timings)
#   - scenes/lib.js, scenes/lib2.js, scenes/beat.js are the shared helpers
set -e

HERE="${0:A:h}"
PROJ_ARG="${1:?usage: record.sh <project> [take ...]}"
shift || true

# Resolve the project directory (a path, or a name under projects/).
if [[ -d "$PROJ_ARG" ]]; then PROJ="${PROJ_ARG:A}"; else PROJ="$HERE/projects/$PROJ_ARG"; fi
[[ -f "$PROJ/video.json" ]] || { echo "no video.json in $PROJ"; exit 1; }

WORK=$(python3 -c "import json,os;print(os.path.expanduser(json.load(open('$PROJ/video.json'))['workDir']))")
mkdir -p "$WORK"/{takes,shots}

# The scene scripts read their sentence timings from a small pointer file.
cat > /tmp/vid/vb-paths.json <<JSON
{ "timings": "$WORK/sentence-timings.json", "project": "$PROJ", "work": "$WORK" }
JSON
[[ -f "$WORK/sentence-timings.json" ]] || {
  echo "missing $WORK/sentence-timings.json - run: pipeline.py align --project $PROJ"
  exit 1
}

SESSION="${SESSION:-onshape-video}"
TAKES=("$@")
if (( ${#TAKES} == 0 )); then
  TAKES=($(python3 -c "
import json;print(' '.join(t['name'] for t in json.load(open('$PROJ/video.json'))['takes']))"))
fi

bundle() {   # bundle <scene-file> <out>
  { sed 's/^module\.exports = .*$//' "$HERE/scenes/lib.js"
    sed 's/^module\.exports = .*$//' "$HERE/scenes/lib2.js"
    cat "$HERE/scenes/beat.js"
    echo 'return await (async () => {'
    cat "$1"
    echo '})();'
  } > "$2"
}

for TAKE in "${TAKES[@]}"; do
  SETUP=$(python3 -c "
import json;d=json.load(open('$PROJ/video.json'))
print(next((t.get('setup','setup-noop') for t in d['takes'] if t['name']=='$TAKE'),'setup-noop'))")
  echo "######## $TAKE (setup: $SETUP) ########"

  echo "-- setup --"
  bundle "$PROJ/setup/$SETUP.js" /tmp/vid/.vs-setup.js
  browser-control execute --session "$SESSION" --file /tmp/vid/.vs-setup.js --json \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
v=d.get('value') or {}
print('  ok:',d.get('ok'),str(v)[:300])
if not d.get('ok'):
    print('  error:',(d.get('text') or '')[:400])
sys.exit(0 if d.get('ok') else 1)"

  echo "-- preflight --"
  browser-control execute --session "$SESSION" --file "$HERE/scenes/preflight.js" --json \
    | python3 -c "import json,sys;d=json.load(sys.stdin);v=d.get('value') or {};print('  ok:',d.get('ok'),'surface',v.get('surface'))"

  echo "-- record --"
  browser-control recording start "$WORK/takes/$TAKE.mp4" --session "$SESSION" \
    --mode cdp --frame-rate 30 --json > "$WORK/takes/$TAKE.start.json" 2>&1

  bundle "$PROJ/takes/$TAKE.js" /tmp/vid/.vs-take.js
  browser-control execute --session "$SESSION" --file /tmp/vid/.vs-take.js --json \
    > "$WORK/takes/$TAKE.exec.json" 2>&1 || true
  python3 -c "
import json
try:
    d=json.load(open('$WORK/takes/$TAKE.exec.json'))
    if not d.get('ok'): print('  take error:', (d.get('text') or '')[:300])
except Exception: pass"

  sleep 1
  browser-control recording stop --session "$SESSION" --json > "$WORK/takes/$TAKE.json" 2>&1

  python3 - "$WORK" "$TAKE" <<'PY'
import json, subprocess, sys, os
work, take = sys.argv[1], sys.argv[2]
base = os.path.join(work, 'takes', take)
try:
    d = json.load(open(base + '.json')); q = d.get('quality', {})
    print(f"  take {take}: {d.get('duration',0)/1000:.1f}s  "
          f"surface {q.get('sourceWidth')}x{q.get('sourceHeight')}  "
          f"frames {q.get('sourceFrameCount')}")
except Exception as e:
    print('  no quality:', e)
try:
    v = (json.load(open(base + '.exec.json')).get('value') or {})
    for m in v.get('marks', []):
        print(f"    {m['n']:18s} {m['rel']:7d}ms")
    if v.get('found'):
        print('    found:', v['found'])
except Exception as e:
    print('  no marks:', e)
PY
done

echo ""
echo "Recordings in $WORK/takes"
echo "Next: python3 $HERE/pipeline.py plan --project $PROJ"
