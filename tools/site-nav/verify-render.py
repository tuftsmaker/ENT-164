#!/usr/bin/env python3
"""Prove the nav actually renders, in a real browser, at real widths.

`apply.py --check` proves the markup matches the spec, and `verify-links.py`
proves the hrefs resolve. Neither can prove the links are *visible*: the nav
once shipped with the links present in the HTML, `display: flex`, and rendered
at zero height, because they sat inside a closed `<details>`. Only a browser
can see that.

So this drives headless Chrome and asks each page, at two widths:

  * are all five main links painted (width and height > 0)?
  * on a narrow screen, does the menu button appear, and does opening it
    reveal the links?

Requires Chrome (same autodetection as scripts/build-class.sh) and a local
server, which it starts itself.

    python3 tools/site-nav/verify-render.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

PAGES = [
    "index.html",
    "syllabus/index.html",
    "about/index.html",
    "onshape-tips/index.html",
    "laser-cutting/index.html",
    "tasks/index.html",
    "tasks/cad-03-cut-a-hole.html",
    "tasks/unit-laser-ready.html",
    "classes/class-03/index.html",
    "classes/class-11/index.html",
]

WIDE, NARROW = 1200, 720
EXPECTED = 5  # Tasks, Workshops, Syllabus, About, + the page's own CTA

PROBE = """
<script>
window.addEventListener('load', function () {
  // A link counts as rendered only if it has a painted box AND does not sit
  // inside a hidden ancestor. checkVisibility() alone is not enough: it misses
  // an ancestor with `visibility: hidden`, which is exactly how the nav broke
  // the first time (a closed <details> hides children whatever CSS says).
  function painted(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
      var cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    }
    if (el.checkVisibility && !el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) {
      return false;
    }
    return true;
  }
  var cb = document.getElementById('nav-toggle');
  if (window.__OPEN_MENU__ && cb) cb.checked = true;
  var out = {
    links: Array.from(document.querySelectorAll('.nav-links > a')).filter(painted)
      .map(function (a) { return a.textContent.trim(); }),
    menuButton: painted(document.querySelector('.nav-toggle-label')),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  };
  var pre = document.createElement('pre'); pre.id = 'probe';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>
"""


def chrome_path() -> str | None:
    for candidate in (
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def measure(chrome: str, rel: str, width: int, open_menu=False) -> dict:
    """Load the page with the probe injected, in a real browser, and read back
    what is painted. The probe is written inside the repo so the page's relative
    asset paths still resolve."""
    probe = PROBE.replace("window.__OPEN_MENU__", "true" if open_menu else "false")
    html = (ROOT / rel).read_text().replace("</body>", probe + "</body>")
    probe_name = f".render-probe-{abs(hash((rel, width, open_menu))) % 10**8}.html"
    probe_path = ROOT / probe_name
    probe_path.write_text(html)
    try:
        proc = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--window-size={width},900", "--virtual-time-budget=3500",
             "--dump-dom", f"http://127.0.0.1:{PORT}/{probe_name}"],
            capture_output=True, text=True, timeout=90,
        )
    finally:
        probe_path.unlink(missing_ok=True)

    m = re.search(r'<pre id="probe">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        return {"error": "probe did not run"}
    import html as html_mod

    return json.loads(html_mod.unescape(m.group(1)))


def main() -> int:
    chrome = chrome_path()
    if not chrome:
        print("no Chrome found — set CHROME_BIN to run this check", file=sys.stderr)
        return 2

    global PORT
    PORT = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.2)
    problems = []
    try:
        for rel in PAGES:
            wide = measure(chrome, rel, WIDE)
            narrow = measure(chrome, rel, NARROW)
            opened = measure(chrome, rel, NARROW, open_menu=True)

            if wide.get("error") or narrow.get("error"):
                problems.append(f"{rel}: probe failed ({wide.get('error') or narrow.get('error')})")
                continue

            n_wide = len(wide["links"])
            if n_wide != EXPECTED:
                problems.append(
                    f"{rel}: {n_wide}/{EXPECTED} links painted at {WIDE}px "
                    f"({', '.join(wide['links']) or 'none'})"
                )
            if wide["menuButton"]:
                problems.append(f"{rel}: the menu button is showing at {WIDE}px")
            if not narrow["menuButton"]:
                problems.append(f"{rel}: no menu button at {NARROW}px")
            if len(opened["links"]) != EXPECTED:
                problems.append(
                    f"{rel}: opening the menu at {NARROW}px shows {len(opened['links'])}/{EXPECTED} links"
                )
            for width, data in ((WIDE, wide), (NARROW, narrow)):
                if data["overflow"]:
                    problems.append(f"{rel}: page scrolls sideways at {width}px")
            status = "ok  " if not any(rel in p for p in problems) else "FAIL"
            print(f"{status} {rel:<34} wide {n_wide}/{EXPECTED} · menu open {len(opened['links'])}/{EXPECTED}")
    finally:
        server.terminate()
        server.wait(timeout=10)

    print()
    if problems:
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} problem(s).")
        return 1
    print(f"all {len(PAGES)} pages render the nav correctly at {WIDE}px and {NARROW}px.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
