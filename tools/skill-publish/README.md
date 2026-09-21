# Class skills for opencode

`skills/` is served by GitHub Pages and consumed by opencode through
`skills.urls`:

```
https://tuftsmaker.github.io/ENT-164/skills/
```

Students add that URL to `opencode.json` once (see `handouts/`), then pick up
changes automatically.

**`skills/` is the source of truth.** There is no separate source tree and no
build output to keep in sync — edit a file in `skills/maker/`, run `rebuild.sh`,
commit, push.

## Editing a skill

```bash
# 1. change something
$EDITOR skills/maker/circuits/led.yml

# 2. rebuild the index (rewrites skills/index.json only)
./tools/skill-publish/rebuild.sh

# 3. publish
git add skills && git commit -m "..." && git push

# 4. verify what students will actually get
curl -s https://tuftsmaker.github.io/ENT-164/skills/index.json
```

Steps 2 and 3 are not optional together. **Editing without rebuilding means
students get nothing** — opencode only re-downloads when a skill's `version`
changes, and that version is a hash of the skill's contents.

## Why the version exists

`skills/index.json` lists every file plus a content hash:

```json
{
  "skills": [
    { "name": "maker", "version": "bc63971a6e02", "files": ["SKILL.md", "..."] }
  ]
}
```

opencode fetches `index.json`, compares each `version` against what it cached,
and only re-downloads when it differs. The hash is derived from the files, so:

- edit a file → new version → students update on next start
- push with no changes → same version → nobody re-downloads anything

You never bump a version by hand. `build-index.py --version X` exists if you
ever need to force one.

## Rules that will bite you

**`files` must list everything.** opencode does not fetch directories
recursively. `rebuild.sh` derives the list from the directory, so this cannot
drift — but never hand-edit `index.json`.

**Jekyll must stay off.** There is a `.nojekyll` file at the repo root and it
is load-bearing for this folder. Without it GitHub Pages runs Jekyll, which
converts `SKILL.md` to HTML (so the `.md` 404s) and skips `bbd/__init__.py`
because it starts with an underscore. opencode needs both served verbatim.
Do not delete `.nojekyll`.

**Failures are silent.** If a file 404s, the skill simply does not appear, with
only a log line on the student's machine. Always curl after pushing, and check
that every file in the index actually returns 200:

```bash
python3 - <<'PY'
import json, urllib.request
base = "https://tuftsmaker.github.io/ENT-164/skills/"
idx = json.load(urllib.request.urlopen(base + "index.json"))
for s in idx["skills"]:
    for rel in s["files"]:
        code = urllib.request.urlopen(f"{base}{s['name']}/{rel}").getcode()
        print(code, rel)
PY
```

## Handouts

`handouts/add-class-tools.html` is the student-facing one-pager. Rebuild the
PDF after editing it:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=handouts/add-class-tools.pdf \
  "file://$PWD/handouts/add-class-tools.html"
```

It is sized for US Letter and must stay on one page. Check before committing:

```bash
pdftotext -f 2 -l 2 handouts/add-class-tools.pdf - | head
```

If that prints anything, content has spilled onto page 2.

## Cache on the student's machine

`~/.cache/opencode/skills/`. Deleting it forces a clean re-fetch, which is the
first thing to try if someone reports stale content.
