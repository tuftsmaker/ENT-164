#!/usr/bin/env python3
"""Apply the student-writing-style skill's punctuation rules to site HTML.

The skill says: no em dashes, use periods or commas. Choosing between them
needs the whole sentence, and a sentence is often split across inline tags
(`<b>Birch plywood</b> — <span>Natural → Wood</span>`), so the tool works in
one offset space: it builds the text stream of the eligible runs, decides each
dash there, and maps the result back into the run the dash came from. Tags,
comments, <style>, <script>, <title> and <pre> are never touched, and en dashes
in ranges (3–5) are left alone.

    python3 tools/writing-pass/dashes.py --dry-run FILE...
    python3 tools/writing-pass/dashes.py --check FILE...
    python3 tools/writing-pass/dashes.py FILE...
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_TAGS = ("style", "script", "title", "pre")
CONJUNCTIONS = {"and", "but", "or", "so", "plus", "then", "yet", "because", "which", "where"}
KEEP_LOWER = {"opencode", "iphone", "ipad", "macos", "ios", "ipados", "esp32", "onshape",
              "inkscape", "micropython", "python", "usb", "wifi", "diy", "llm", "ai"}
TOKEN = re.compile(r"(<[^>]+>)")
DASH = re.compile(r"[ \t]*—[ \t]*")


def _capitalize(word: str) -> str:
    if word.lower() in KEEP_LOWER or not word[:1].islower():
        return word
    return word[:1].upper() + word[1:]


def operations(stream: str) -> list:
    """(start, end, replacement) for every change, in stream offsets."""
    ops = []
    for match in DASH.finditer(stream):
        # a matched pair sits close together; a lone dash in the next list item does not
        paired = bool(DASH.search(stream[max(0, match.start() - 50):match.start()])
                      or DASH.search(stream[match.end():match.end() + 50]))
        rest = stream[match.end():]
        first = re.match(r"\S+", rest)
        first = first.group(0).strip(".,;:!?\"')*") if first else ""
        if paired:
            mark = ", "
        elif not rest.strip():
            mark = ": "                       # the value follows in the next element
        elif first and first.lower() in CONJUNCTIONS:
            mark = ", "
        elif rest.rstrip().endswith(":"):
            mark = ", "
        else:
            mark = ". "
        if mark == ". ":
            word = re.search(r"[A-Za-z]", rest)
            if word:
                index = match.end() + word.start()
                ops.append((index, index + 1, _capitalize(stream[index:index + 1])))
        ops.append((match.start(), match.end(), mark))
    for match in re.finditer(r"!+", stream):
        # the skill bans exclamation points; a period, and the next word keeps its capital
        ops.append((match.start(), match.end(), "."))
        word = re.search(r"[A-Za-z]", stream[match.end():])
        if word:
            index = match.end() + word.start()
            ops.append((index, index + 1, _capitalize(stream[index:index + 1])))
    return sorted(ops)


def apply_ops(stream: str, ops: list) -> str:
    for start, end, replacement in reversed(ops):
        stream = stream[:start] + replacement + stream[end:]
    return stream


def fix_html(html: str) -> str:
    tokens = TOKEN.split(html)
    skip = 0
    runs = []                      # (token index, text) for eligible runs
    for index, token in enumerate(tokens):
        if token.startswith("<"):
            match = re.match(r"</?\s*([a-zA-Z0-9]+)", token)
            tag = match.group(1).lower() if match else ""
            if tag in SKIP_TAGS:
                skip += -1 if token.startswith("</") else 1
        elif token and not skip:
            runs.append((index, token))
    if not runs:
        return html
    stream = "".join(text for _, text in runs)
    if "—" not in stream and "!" not in stream:
        return html
    ops = operations(stream)
    if not ops:
        return html

    # walk the runs, applying the operations that fall inside each
    out = list(tokens)
    offset = 0
    for index, text in runs:
        start = offset
        offset += len(text)
        local = [(a - start, b - start, c) for a, b, c in ops if start <= a and b <= offset]
        piece = text
        for begin, end, replacement in reversed(local):
            piece = piece[:begin] + replacement + piece[end:]
        out[index] = piece
    html = "".join(out)
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    dirty = 0
    for name in args.files:
        path = Path(name)
        before = path.read_text(encoding="utf-8")
        after = fix_html(before)
        if before == after:
            print(f"  {name}: clean")
            continue
        dirty += 1
        before_dashes, after_dashes = len(DASH.findall(before)), len(DASH.findall(after))
        print(f"  {name}: dashes {before_dashes} -> {after_dashes}")
        if args.dry_run:
            for line_before, line_after in zip(before.splitlines(), after.splitlines()):
                if line_before != line_after:
                    print(f"      - {line_before.strip()[:150]}")
                    print(f"      + {line_after.strip()[:150]}")
        elif not args.check:
            path.write_text(after, encoding="utf-8")
    return 1 if args.check and dirty else 0


if __name__ == "__main__":
    raise SystemExit(main())
