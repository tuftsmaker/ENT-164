// Companion to lib.js: visible DOM cursor + smooth motion + text targeting.
// Optimised: the in-page animation defines pacing; the real pointer is driven
// with few coarse steps so each moveTo costs ~1 round trip, not ~30.

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cursorInject(size = 26) {
  await page.evaluate((s) => {
    if (document.getElementById('__vc_cursor')) return;
    const d = document.createElement('div');
    d.id = '__vc_cursor';
    d.style.cssText = 'position:fixed;left:0;top:0;width:' + s + 'px;height:' + s + 'px;'
      + 'z-index:2147483646;pointer-events:none;will-change:transform;'
      + 'transform:translate3d(-100px,-100px,0);';
    d.innerHTML = '<svg width="' + s + '" height="' + s + '" viewBox="0 0 26 26">'
      + '<path d="M4.5 1.2 L4.5 20.4 L9.5 15.7 L12.6 22.6 L15.9 21.1 L12.8 14.3 L19.6 14.3 Z" '
      + 'fill="#ffffff" stroke="#0d0d0d" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(d);
    window.__vcCur = [960, 540];
    window.__vcSet = (x, y) => { window.__vcCur = [x, y]; d.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)'; };
  }, size);
}

// The BC badge lives in a shadow root that declares
// `:host { all: initial !important }`, so document-level !important rules
// cannot hide it. Instead, move it into a hidden wrapper: a `display:none`
// ancestor suppresses rendering regardless of the host's own styles.
// A MutationObserver moves it the moment it (re)appears, so it never paints.
async function hideBadge() {
  await page.evaluate(() => {
    const move = () => {
      let box = document.getElementById('__vc_hidden_bc');
      if (!box) {
        box = document.createElement('div');
        box.id = '__vc_hidden_bc';
        box.style.cssText = 'display:none !important;visibility:hidden !important;'
          + 'position:absolute !important;left:-10000px !important;top:-10000px !important;'
          + 'width:0 !important;height:0 !important;overflow:hidden !important;';
        document.documentElement.appendChild(box);
      }
      document.querySelectorAll('[id^="__browser_control"]').forEach((el) => {
        if (el.parentElement !== box) box.appendChild(el);
      });
    };
    move();
    if (!window.__vcSuppressObs) {
      window.__vcSuppressObs = new MutationObserver(move);
      window.__vcSuppressObs.observe(document.documentElement, { childList: true, subtree: true });
    }
    if (!window.__vcSuppressTimer) window.__vcSuppressTimer = setInterval(move, 250);
  });
}

const _ptr = { x: 960, y: 540 };

// Animate the visible cursor over `durMs`. The real pointer is moved with a
// small number of coarse steps, concurrently.
async function moveTo(x, y, durMs = 620, opts = {}) {
  const from = await page.evaluate(() => window.__vcCur || [960, 540]);
  const sx = from[0], sy = from[1];
  const dur = Math.max(60, durMs | 0);

  // One round trip: run the whole animation in-page on rAF.
  const animP = page.evaluate(({ sx, sy, x, y, dur }) => new Promise((res) => {
    const t0 = performance.now();
    const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
    function step() {
      const t = Math.min(1, (performance.now() - t0) / dur);
      window.__vcSet(sx + (x - sx) * ease(t), sy + (y - sy) * ease(t));
      if (t < 1) requestAnimationFrame(step); else res(true);
    }
    requestAnimationFrame(step);
  }), { sx, sy, x, y, dur });

  // Real pointer: coarse steps, dispatched quickly (needed for hover state).
  const nSteps = opts.steps || 4;
  const ptrP = (async () => {
    for (let i = 1; i <= nSteps; i++) {
      const t = i / nSteps;
      const px = sx + (x - sx) * t, py = sy + (y - sy) * t;
      await page.mouse.move(px, py, { steps: 1 });
      if (i < nSteps) await sleep(Math.min(60, dur / nSteps * 0.5));
    }
  })();

  await Promise.all([animP, ptrP]);
  _ptr.x = x; _ptr.y = y;
}

async function clickAt(x, y, settle = 300, moveMs = 460) {
  // The click may itself trigger a navigation; tolerate context destruction.
  try { await moveTo(x, y, moveMs); } catch (e) { /* navigating */ }
  try { await P(90); } catch (e) {}
  try { await page.mouse.down(); await P(70); await page.mouse.up(); } catch (e) { /* navigating */ }
  try {
    await page.evaluate(() => {
      const c = window.__vcCur || [0, 0];
      const r = document.createElement('div');
      r.style.cssText = 'position:fixed;left:0;top:0;width:26px;height:26px;border-radius:50%;'
        + 'border:2.5px solid rgba(255,255,255,0.95);box-shadow:0 0 0 1.5px rgba(0,0,0,0.5);'
        + 'pointer-events:none;z-index:2147483645;'
        + 'transform:translate3d(' + (c[0] + 4) + 'px,' + (c[1] + 4) + 'px,0) scale(0.5);'
        + 'opacity:0.95;transition:transform 360ms ease-out, opacity 360ms ease-out;';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => {
        r.style.transform = 'translate3d(' + (c[0] + 4) + 'px,' + (c[1] + 4) + 'px,0) scale(2.2)';
        r.style.opacity = '0';
      });
      setTimeout(() => r.remove(), 640);
    });
  } catch (e) { /* navigating */ }
  try { await P(settle); } catch (e) {}
}

async function rightClickAt(x, y, settle = 500, moveMs = 460) {
  await moveTo(x, y, moveMs);
  await P(120);
  await page.mouse.down({ button: 'right' });
  await P(70);
  await page.mouse.up({ button: 'right' });
  await P(settle);
}

async function boxOf(text, opts = {}) {
  return await page.evaluate(({ text, maxX, exact, maxY, minY }) => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const all = Array.from(document.querySelectorAll('*')).filter(vis);
    const cands = all.filter((e) => {
      const t = (e.innerText || '').trim();
      const ok = exact ? t === text : t.includes(text);
      if (!ok) return false;
      const r = e.getBoundingClientRect();
      if (maxX != null && r.x > maxX) return false;
      if (maxY != null && r.y > maxY) return false;
      if (minY != null && r.y < minY) return false;
      return true;
    });
    if (!cands.length) return null;
    cands.sort((a, b) => {
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      return ra.width * ra.height - rb.width * rb.height;
    });
    const r = cands[0].getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, { text, maxX: opts.maxX ?? null, maxY: opts.maxY ?? null, minY: opts.minY ?? null, exact: opts.exact ?? true });
}

async function clickText(text, opts = {}) {
  const b = await boxOf(text, opts);
  if (!b) throw new Error('not found: ' + text);
  await clickAt(b.x + b.w / 2, b.y + b.h / 2, opts.settle ?? 320, opts.moveMs ?? 460);
  return b;
}

async function rightClickText(text, opts = {}) {
  const b = await boxOf(text, opts);
  if (!b) throw new Error('not found: ' + text);
  await rightClickAt(b.x + b.w / 2, b.y + b.h / 2, opts.settle ?? 500, opts.moveMs ?? 460);
  return b;
}

async function hideCursor() { await page.evaluate(() => { const d = document.getElementById('__vc_cursor'); if (d) d.style.display = 'none'; }); }async function showCursor() { await page.evaluate(() => { const d = document.getElementById('__vc_cursor'); if (d) d.style.display = ''; }); }

// Click a button inside the currently open modal.
async function modalButton(label, settle = 600) {
  const b = await page.evaluate((lab) => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const b = Array.from(document.querySelectorAll('.modal button, .modal a.btn')).filter(vis)
      .find((e) => new RegExp('^' + lab + '$', 'i').test((e.innerText || '').trim()));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, label);
  if (!b) return null;
  await clickAt(b.x + b.w / 2, b.y + b.h / 2, settle, 420);
  return b;
}

// Toolbar/tool buttons: match by data-bs-original-title, then by label text,
// then by a substring of the title (so "Create new sketch (shift+s)" matches
// both "Sketch" and "Create new sketch").
async function toolBtn(name, opts = {}) {
  const b = await page.evaluate(({ n, substr }) => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const titled = Array.from(document.querySelectorAll('[data-bs-original-title]')).filter(vis)
      .filter((e) => {
        const t = (e.getAttribute('data-bs-original-title') || '').trim();
        if (t === n) return true;
        if (t === n + '\u2026') return true;
        if (t.startsWith(n + ' (')) return true;
        if (substr && t.toLowerCase().includes(n.toLowerCase()) && /\(|shift\+|cmd\+|ctrl\+|\b[a-z]\)$/.test(t)) return true;
        return false;
      });
    if (titled.length) {
      // Prefer the smallest matching element (the innermost button).
      titled.sort((a, b2) => {
        const ra = a.getBoundingClientRect(), rb = b2.getBoundingClientRect();
        return ra.width * ra.height - rb.width * rb.height;
      });
      const r = titled[0].getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height, via: 'title:' + (titled[0].getAttribute('data-bs-original-title') || '') };
    }
    const btns = Array.from(document.querySelectorAll('button, [role=button], .tool, .toolbar-item')).filter(vis);
    const byText = btns.find((e) => {
      const t = (e.innerText || '').trim();
      if (t === n || t === n + '\u2026') return true;
      if (substr && t.toLowerCase().includes(n.toLowerCase())) return true;
      return false;
    });
    if (byText) {
      const r = byText.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height, via: 'text' };
    }
    return null;
  }, { n: name, substr: opts.substr !== false });
  return b;
}

async function clickToolBtn(name, opts = {}) {
  const b = await toolBtn(name, opts);
  if (!b) throw new Error('tool button not found: ' + name);
  await clickAt(b.x + b.w / 2, b.y + b.h / 2, opts.settle ?? 800, opts.moveMs ?? 480);
  return b;
}

// Type into whatever currently has focus (dimension editors are transient).
async function typeKeys(seq, delay = 55) {
  for (const k of seq) {
    if (typeof k === 'string' && k.length > 1 && !/^(Tab|Enter|Escape|Backspace|Delete)$/.test(k)) {
      await page.keyboard.type(k, { delay });
    } else {
      await page.keyboard.press(k);
    }
    await P(70);
  }
}

// Orbit the 3D view by right-dragging (Onshape rotates on right-drag; a
// right-click without movement would open the context menu instead).
async function orbit(x1, y1, x2, y2, durMs = 1500) {
  await moveTo(x1, y1, 550);
  await P(220);
  await page.mouse.down({ button: 'right' });
  await P(130);
  const steps = Math.max(10, Math.round(durMs / 90));
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    await page.mouse.move(x1 + (x2 - x1) * e, y1 + (y2 - y1) * e, { steps: 1 });
    await P(Math.round(durMs / steps));
  }
  await P(150);
  await page.mouse.up({ button: 'right' });
  await P(350);
}
