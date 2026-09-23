#!/usr/bin/env python3
"""Generated PDF <-> source sync bookkeeping.

Two kinds of generated PDF live in this repo:

  * class decks  - classes/<class>/slides.html + shots/ -> the deck PDF
  * the syllabus - syllabus/index.html                   -> the syllabus PDF

Each one records a source hash (its page, the shared assets it references, and
its image tree when it has one) next to the PDF when it is built. `check`
recomputes the hash and fails when a committed PDF no longer matches its
sources. That is what keeps the syllabus PDF honest: it is generated from the
web page, never edited by hand.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ASSET_REF = re.compile(r'(?:src|href)="([^"]+)"')

# A class deck and the syllabus differ only in which page is the source, whether
# there is an image tree beside it, and what the bookkeeping file is called.
DECK = {"page": "slides.html", "tree": "shots", "buildinfo": "slides.buildinfo"}
SYLLABUS = {"page": "index.html", "tree": None, "buildinfo": "syllabus.buildinfo"}

SYLLABUS_DIR = os.path.join("syllabus")


def profile_for(page_dir):
    """Which profile a directory uses. Only the syllabus is not a deck."""
    if os.path.isfile(os.path.join(page_dir, DECK["page"])):
        return DECK
    if os.path.basename(os.path.abspath(page_dir)) == "syllabus":
        return SYLLABUS
    raise SystemExit(f"cannot tell what kind of PDF {page_dir} generates")


def referenced_assets(page_dir, root, profile):
    """The shared assets/ files this page actually loads.

    Used both to hash a document and to decide whether a commit touches it: a
    change to a logo a deck embeds invalidates that deck, and a change to a
    stylesheet the syllabus loads invalidates the syllabus.
    """
    page = os.path.join(page_dir, profile["page"])
    with open(page, "rb") as f:
        page_html = f.read().decode("utf-8", "replace")
    assets_root = os.path.abspath(os.path.join(root, "assets"))
    refs = set()
    for ref in ASSET_REF.findall(page_html):
        if ref.startswith(("http:", "https:", "data:", "#", "mailto:")):
            continue
        path = os.path.abspath(os.path.normpath(os.path.join(page_dir, ref)))
        if os.path.isfile(path) and os.path.commonpath([path, assets_root]) == assets_root:
            refs.add(path)
    return refs


def source_hash(page_dir, root, profile=DECK):
    h = hashlib.sha256()

    def add_file(path):
        h.update(os.path.relpath(path, root).encode() + b"\0")
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)

    def add_tree(path):
        if not path or not os.path.isdir(path):
            return
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames.sort()
            for name in sorted(filenames):
                if name == ".DS_Store":
                    continue
                add_file(os.path.join(dirpath, name))

    page = os.path.join(page_dir, profile["page"])
    if not os.path.isfile(page):
        raise SystemExit(f"no {profile['page']} in {page_dir}")
    with open(page, "rb") as f:
        page_html = f.read()
    h.update(profile["page"].encode() + b"\0")
    h.update(page_html)
    add_tree(os.path.join(page_dir, profile["tree"]) if profile["tree"] else None)

    # Only the files under assets/ that this page actually references count, so
    # style changes elsewhere on the site do not invalidate it. A shared file
    # legitimately invalidates every page that loads it - the syllabus loads
    # site.css, so a change there means the syllabus PDF is rebuilt too.
    for path in sorted(referenced_assets(page_dir, root, profile)):
        add_file(path)
    return h.hexdigest()


def pdf_pages(pdf_path):
    if shutil.which("pdfinfo"):
        try:
            out = subprocess.run(
                ["pdfinfo", pdf_path], capture_output=True, text=True, check=True
            ).stdout
            for line in out.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split()[1])
        except (subprocess.CalledProcessError, ValueError):
            pass
    return None


def write(page_dir, pdf_name, profile=None):
    page_dir = os.path.abspath(page_dir)
    profile = profile or profile_for(page_dir)
    root = os.path.dirname(os.path.dirname(page_dir))
    pdf_path = os.path.join(page_dir, pdf_name)
    if not (os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0):
        raise SystemExit(f"pdf missing or empty: {pdf_path}")
    info = {
        "doc": os.path.basename(page_dir),
        "pdf": pdf_name,
        "source_hash": source_hash(page_dir, root, profile),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": pdf_pages(pdf_path),
        "pdf_bytes": os.path.getsize(pdf_path),
    }
    path = os.path.join(page_dir, profile["buildinfo"])
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
        f.write("\n")
    return info


def check(targets):
    """`targets` is [(page_dir, profile), ...]."""
    stale = []
    for page_dir, profile in targets:
        page_dir = os.path.abspath(page_dir)
        root = os.path.dirname(os.path.dirname(page_dir))
        name = os.path.relpath(page_dir, root)
        path = os.path.join(page_dir, profile["buildinfo"])
        if not os.path.isfile(path):
            stale.append(f"{name}: no {profile['buildinfo']} - run {build_hint(profile)}")
            continue
        with open(path) as f:
            info = json.load(f)
        pdf_path = os.path.join(page_dir, info.get("pdf", ""))
        if not os.path.isfile(pdf_path):
            stale.append(f"{name}: {info.get('pdf')} is missing")
            continue
        if os.path.getsize(pdf_path) != info.get("pdf_bytes"):
            stale.append(
                f"{name}: {info['pdf']} was modified after its last build "
                f"({os.path.getsize(pdf_path)} != {info['pdf_bytes']} bytes)"
            )
            continue
        current = source_hash(page_dir, root, profile)
        if current != info.get("source_hash"):
            stale.append(
                f"{name}: sources changed since {info.get('built_at')} - "
                f"run {build_hint(profile)}"
            )
    if stale:
        print("Generated PDFs out of sync:")
        for line in stale:
            print(f"  - {line}")
        return 1
    print(f"Generated PDFs in sync ({len(targets)} document(s)).")
    return 0


def build_hint(profile):
    return "scripts/build-syllabus.sh" if profile is SYLLABUS else "scripts/build-class.sh <class>"


def targets(root, args):
    """The documents a `check` run should cover.

    `--all` means every class deck, which is what build-class.sh has always
    meant; the syllabus is checked by build-syllabus.sh, so that a failure
    names the one document that is stale.
    """
    classes_dir = os.path.join(root, "classes")

    def decks():
        if not os.path.isdir(classes_dir):
            return []
        return [
            (os.path.join(classes_dir, d), DECK)
            for d in sorted(os.listdir(classes_dir))
            if os.path.isfile(os.path.join(classes_dir, d, DECK["page"]))
        ]

    if not args or args[0] == "--all":
        return decks()

    out = []
    for arg in args:
        if os.path.isdir(arg):
            page_dir = arg.rstrip("/")
        elif os.path.isdir(os.path.join(classes_dir, arg)):
            page_dir = os.path.join(classes_dir, arg)
        else:
            page_dir = arg
        out.append((page_dir, profile_for(page_dir)))
    return out


def read_buildinfo(page_dir, profile):
    path = os.path.join(os.path.abspath(page_dir), profile["buildinfo"])
    if not os.path.isfile(path):
        raise SystemExit(f"no {profile['buildinfo']} in {page_dir}")
    with open(path) as f:
        return json.load(f)


def chrome_available():
    """True when a Chrome/Chromium binary can be found, the same way the build
    scripts find one, so a caller can fail early instead of printing nothing."""
    if os.environ.get("CHROME_BIN") and os.access(os.environ["CHROME_BIN"], os.X_OK):
        return True
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return any(c and os.access(c, os.X_OK) for c in candidates)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if cmd == "hash":
        page_dir = os.path.abspath(sys.argv[2])
        print(source_hash(page_dir, root, profile_for(page_dir)))
    elif cmd == "write":
        info = write(sys.argv[2], sys.argv[3])
        print(f"{info['doc']}: {info['pages'] or '?'} pages, "
              f"{info['pdf_bytes']} bytes, source {info['source_hash'][:12]}")
    elif cmd == "check":
        sys.exit(check(targets(root, sys.argv[2:])))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
