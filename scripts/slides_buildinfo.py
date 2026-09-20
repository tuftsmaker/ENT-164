#!/usr/bin/env python3
"""Slide PDF <-> source sync bookkeeping.

Each class deck records a source hash (slides.html + shots/ + shared
assets/) in classes/<class>/slides.buildinfo when its PDF is built.
`check` recomputes the hash and fails when a committed PDF no longer
matches its sources.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

BUILDINFO = "slides.buildinfo"


def source_hash(class_dir, root):
    h = hashlib.sha256()

    def add_tree(path):
        if not os.path.isdir(path):
            return
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames.sort()
            for name in sorted(filenames):
                if name == ".DS_Store":
                    continue
                p = os.path.join(dirpath, name)
                h.update(os.path.relpath(p, root).encode() + b"\0")
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)

    slides = os.path.join(class_dir, "slides.html")
    if not os.path.isfile(slides):
        raise SystemExit(f"no slides.html in {class_dir}")
    h.update(b"slides.html\0")
    with open(slides, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    add_tree(os.path.join(class_dir, "shots"))
    add_tree(os.path.join(root, "assets"))
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


def write(class_dir, pdf_name):
    class_dir = os.path.abspath(class_dir)
    root = os.path.dirname(os.path.dirname(class_dir))
    pdf_path = os.path.join(class_dir, pdf_name)
    if not (os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0):
        raise SystemExit(f"pdf missing or empty: {pdf_path}")
    info = {
        "class": os.path.basename(class_dir),
        "pdf": pdf_name,
        "source_hash": source_hash(class_dir, root),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": pdf_pages(pdf_path),
        "pdf_bytes": os.path.getsize(pdf_path),
    }
    path = os.path.join(class_dir, BUILDINFO)
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
        f.write("\n")
    return info


def check(class_dirs):
    stale = []
    for class_dir in class_dirs:
        class_dir = os.path.abspath(class_dir)
        root = os.path.dirname(os.path.dirname(class_dir))
        name = os.path.basename(class_dir)
        path = os.path.join(class_dir, BUILDINFO)
        if not os.path.isfile(path):
            stale.append(f"{name}: no {BUILDINFO} - run scripts/build-class.sh {name}")
            continue
        with open(path) as f:
            info = json.load(f)
        pdf_path = os.path.join(class_dir, info.get("pdf", ""))
        if not os.path.isfile(pdf_path):
            stale.append(f"{name}: {info.get('pdf')} is missing")
            continue
        if os.path.getsize(pdf_path) != info.get("pdf_bytes"):
            stale.append(
                f"{name}: {info['pdf']} was modified after its last build "
                f"({os.path.getsize(pdf_path)} != {info['pdf_bytes']} bytes)"
            )
            continue
        current = source_hash(class_dir, root)
        if current != info.get("source_hash"):
            stale.append(
                f"{name}: sources changed since {info.get('built_at')} - "
                f"run scripts/build-class.sh {name}"
            )
    if stale:
        print("Slide PDFs out of sync:")
        for line in stale:
            print(f"  - {line}")
        return 1
    print(f"Slide PDFs in sync ({len(class_dirs)} class(es)).")
    return 0


def class_dirs(root, args):
    classes_dir = os.path.join(root, "classes")
    if not args or args == ["--all"]:
        dirs = [
            os.path.join(classes_dir, d)
            for d in sorted(os.listdir(classes_dir))
            if os.path.isfile(os.path.join(classes_dir, d, "slides.html"))
        ] if os.path.isdir(classes_dir) else []
        return dirs
    out = []
    for arg in args:
        if os.path.isdir(arg):
            out.append(arg.rstrip("/"))
        else:
            out.append(os.path.join(classes_dir, arg))
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if cmd == "hash":
        print(source_hash(os.path.abspath(sys.argv[2]), root))
    elif cmd == "write":
        info = write(sys.argv[2], sys.argv[3])
        print(f"{info['class']}: {info['pages'] or '?'} pages, "
              f"{info['pdf_bytes']} bytes, source {info['source_hash'][:12]}")
    elif cmd == "check":
        sys.exit(check(class_dirs(root, sys.argv[2:])))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
