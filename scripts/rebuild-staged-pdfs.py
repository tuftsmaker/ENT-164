#!/usr/bin/env python3
"""Rebuild the generated PDFs that a commit invalidates.

Called by the pre-commit hook (scripts/git-hooks/pre-commit). A commit that
edits a deck's slides, its shots, or an image it embeds must carry the rebuilt
PDF, or CI fails and the published site serves a PDF that disagrees with its
page. Rather than leaving that to memory, this finds the affected documents,
rebuilds each, and stages the result.

What counts as affected is the same rule the source hash uses: a document's page,
its image tree, and the shared assets/ files it actually references. So editing
assets/site.css rebuilds the syllabus (which loads it) and not the decks (which
do not); editing a logo rebuilds every deck that embeds it.

    scripts/rebuild-staged-pdfs.py --dry-run   # report, change nothing
    scripts/rebuild-staged-pdfs.py             # rebuild and stage
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pdf_buildinfo as pb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def staged_paths() -> list[str]:
    """Staged paths, repo-relative. NUL-separated so spaces survive."""
    out = subprocess.run(
        ["git", "-C", ROOT, "diff", "--cached", "--name-only", "--diff-filter=d", "-z"],
        capture_output=True, check=True,
    ).stdout
    return [p.decode() for p in out.split(b"\0") if p]


def documents(root: str) -> list[tuple[str, dict]]:
    """Every document with a generated PDF."""
    docs = [(d, pb.DECK) for d, _ in pb.targets(root, ["--all"])]
    syllabus = os.path.join(root, pb.SYLLABUS_DIR)
    if os.path.isfile(os.path.join(syllabus, pb.SYLLABUS["page"])):
        docs.append((syllabus, pb.SYLLABUS))
    return docs


def inputs_for(page_dir: str, root: str, profile: dict) -> set[str]:
    """The repo-relative paths that invalidate this document."""
    rel = lambda p: os.path.relpath(p, root)  # noqa: E731
    inputs = {rel(os.path.join(page_dir, profile["page"]))}
    tree = profile["tree"]
    if tree and os.path.isdir(os.path.join(page_dir, tree)):
        inputs.add(rel(os.path.join(page_dir, tree)))
    inputs.update(rel(p) for p in pb.referenced_assets(page_dir, root, profile))
    return inputs


def touched(staged: list[str], inputs: set[str]) -> list[str]:
    """Which staged paths fall inside this document's inputs."""
    hits = []
    for path in staged:
        for dep in inputs:
            if path == dep or path.startswith(dep.rstrip("/") + "/"):
                hits.append(path)
                break
    return hits


def in_sync(page_dir: str, profile: dict) -> bool:
    """True when the committed PDF already matches the working tree sources.

    Chrome's print-to-pdf is not byte-deterministic (it embeds a timestamp), so
    rebuilding an up-to-date document would produce a different file every
    commit: noise in the history and growth in the repo. When the document is
    already in sync there is nothing to rebuild, so skip it.
    """
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return pb.check([(page_dir, profile)]) == 0


def unstaged_inputs(page_dir: str, inputs: set[str]) -> list[str]:
    """Staged-source changes that the commit would NOT include.

    Rebuilding with these present would bake uncommitted edits into the PDF,
    leaving the committed PDF disagreeing with the committed page - the exact
    failure this hook exists to prevent - so the hook refuses instead.
    """
    out = subprocess.run(
        ["git", "-C", ROOT, "diff", "--name-only", "-z"],
        capture_output=True, check=True,
    ).stdout
    unstaged = {p.decode() for p in out.split(b"\0") if p}
    return sorted(unstaged & inputs)


def build_command(page_dir: str, profile: dict) -> list[str]:
    if profile is pb.SYLLABUS:
        return [os.path.join(ROOT, "scripts", "build-syllabus.sh")]
    return [os.path.join(ROOT, "scripts", "build-class.sh"), os.path.basename(page_dir)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    args = ap.parse_args()

    staged = staged_paths()
    if not staged:
        return 0

    todo = []
    for page_dir, profile in documents(ROOT):
        hits = touched(staged, inputs_for(page_dir, ROOT, profile))
        if hits:
            todo.append((page_dir, profile, hits))

    if not todo:
        return 0

    # A PDF staged on its own is already built; only the sources matter. A
    # document already in sync needs nothing, and rebuilding it would only churn
    # a non-deterministic file.
    rebuild = []
    skipped = []
    for page_dir, profile, hits in todo:
        sources = [h for h in hits if not h.endswith((".pdf", ".buildinfo"))]
        if not sources:
            continue
        if in_sync(page_dir, profile):
            skipped.append(os.path.relpath(page_dir, ROOT))
            continue
        rebuild.append((page_dir, profile, sources))

    if not rebuild:
        # The common case on a commit that only touches an up-to-date document:
        # say nothing, so the hook is quiet unless it has work to do.
        return 0

    # Refuse to bake uncommitted edits into a PDF: the committed PDF would then
    # disagree with the committed page, which is worse than a stale PDF.
    dirty = []
    for page_dir, profile, _ in rebuild:
        stray = unstaged_inputs(page_dir, inputs_for(page_dir, ROOT, profile))
        if stray:
            dirty.append((page_dir, stray))
    if dirty:
        print("Refusing to rebuild: these sources have unstaged changes, so the")
        print("PDF would not match what this commit contains:")
        for page_dir, stray in dirty:
            print(f"  {os.path.relpath(page_dir, ROOT)}")
            for s in stray[:4]:
                print(f"      {s}")
        print("\nStage them, or commit with --no-verify.")
        return 1

    print("Generated PDFs need rebuilding for this commit:")
    for page_dir, profile, sources in rebuild:
        name = os.path.relpath(page_dir, ROOT)
        print(f"  {name}  ({len(sources)} changed source(s))")
        for s in sorted(sources)[:4]:
            print(f"      {s}")
        if len(sources) > 4:
            print(f"      ... and {len(sources) - 4} more")
    if skipped:
        print(f"  (already in sync, skipped: {', '.join(sorted(skipped))})")

    if args.dry_run:
        print("\n--dry-run: nothing rebuilt.")
        if not pb.chrome_available():
            print("note: no Chrome/Chromium found; set CHROME_BIN to rebuild.")
        return 0

    if not pb.chrome_available():
        print("\nerror: no Chrome/Chromium found; set CHROME_BIN.", file=sys.stderr)
        print("       Rebuild the PDFs above, or commit with --no-verify.", file=sys.stderr)
        return 1

    for page_dir, profile, _ in rebuild:
        name = os.path.relpath(page_dir, ROOT)
        cmd = build_command(page_dir, profile)
        print(f"  rebuilding {name} ...")
        res = subprocess.run(cmd, cwd=ROOT)
        if res.returncode != 0:
            print(f"error: {name}: rebuild failed", file=sys.stderr)
            return 1
        pdf_name = pb.read_buildinfo(page_dir, profile)["pdf"]
        subprocess.run(
            ["git", "-C", ROOT, "add",
             os.path.join(name, pdf_name),
             os.path.join(name, profile["buildinfo"])],
            check=True,
        )

    print(f"\n{len(rebuild)} PDF(s) rebuilt and staged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
