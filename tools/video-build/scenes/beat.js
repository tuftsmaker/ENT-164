// Beat scheduler + narration timing helpers (Deepgram clips).
// P and moveTo come from lib.js / lib2.js.

const _fs = (typeof fs !== 'undefined' && fs) || modules.fs;
// record.sh writes a pointer file so the scenes do not hard-code paths.
function _timings() {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    if (ptr.timings) return JSON.parse(_fs.readFileSync(ptr.timings, 'utf8'));
  } catch (e) { /* fall through */ }
  return JSON.parse(_fs.readFileSync('/tmp/vid/sentence-timings-dg.json', 'utf8'));
}
const TIM = _timings();

// Sentence timing within a scene: sent('s07_dimensions', 2) -> [start, end]
function sent(sid, i) {
  const s = TIM[sid].sentences[i];
  return s ? [s.start, s.end] : [0, TIM[sid].duration];
}
function sceneDur(sid) { return TIM[sid].duration; }

// Offsets of scenes within a take.
function offs(sids) {
  const o = {};
  let t = 0;
  for (const s of sids) { o[s] = t; t += TIM[s].duration; }
  return o;
}
function takeDur(sids) { return sids.reduce((a, s) => a + TIM[s].duration, 0); }

// Absolute (take-relative) time of sentence i of scene sid.
function at(o, sid, i) { return o[sid] + sent(sid, i)[0]; }
function until(o, sid, i) { return o[sid] + sent(sid, i)[1]; }

function Beat(durationSec, name) {
  const t0 = Date.now();
  const marks = [];
  let lastAt = -1;
  const api = {
    name, t0, durationSec, marks,
    elapsed: () => (Date.now() - t0) / 1000,
    async at(sec) {
      if (sec < lastAt) throw new Error('beat backwards: ' + name + ' ' + sec + ' < ' + lastAt);
      lastAt = sec;
      const wait = sec * 1000 - (Date.now() - t0);
      if (wait > 1) await P(Math.round(wait));
    },
    mark: (n) => marks.push({ n, rel: Date.now() - t0, wall: Date.now() }),
  };
  return api;
}

async function scenePrep() {
  await hideBadge();
  await cursorInject();
  await P(120);
}

// Close any open sketch feature dialog and delete all sketches.
async function cleanStudio() {
  for (let i = 0; i < 3; i++) {
    const ok = await page.evaluate(() => {
      const el = document.querySelector('#feature-dialog .ns-dialog-button-ok');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return (r.width > 0 && r.height > 0) ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
    });
    if (!ok) break;
    await page.mouse.move(ok.x + ok.w / 2, ok.y + ok.h / 2, { steps: 5 });
    await P(180); await page.mouse.down(); await P(70); await page.mouse.up(); await P(1200);
  }
  await esc(); await P(250);
  for (let pass = 0; pass < 10; pass++) {
    const row = await page.evaluate(() => {
      const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      const rows = Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis);
      const hit = rows.find((e) => /^Sketch \d+$/.test((e.innerText || '').trim()) && e.getBoundingClientRect().x < 300);
      if (!hit) return null;
      const r = hit.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    });
    if (!row) break;
    await page.mouse.move(row.x + row.w / 2, row.y + row.h / 2, { steps: 5 });
    await P(240);
    await page.mouse.down({ button: 'right' }); await P(80); await page.mouse.up({ button: 'right' });
    await P(650);
    const del = await page.evaluate(() => {
      const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      const hit = Array.from(document.querySelectorAll('*')).filter(vis)
        .find((e) => (e.innerText || '').trim() === 'Delete' && e.children.length === 0);
      if (!hit) return null;
      const r = hit.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    });
    if (!del) { await esc(); break; }
    await page.mouse.move(del.x + del.w / 2, del.y + del.h / 2, { steps: 4 });
    await P(180); await page.mouse.down(); await P(70); await page.mouse.up(); await P(1100);
    await esc(); await P(250);
  }
}

// Create a sketch on the TOP plane (select the datum first) and set the
// standard framing: canonical top view via the view cube, then f (zoom to
// fit) with an empty sketch. This keeps the "Top" label upright and the
// framing reproducible.
async function newTopSketchFramed() {
  // Normalise the Part Studio camera first: an upright, zoomed-to-fit view
  // before entering the sketch keeps the sketch view upright.
  await esc(); await P(250);
  await page.keyboard.press('f'); await P(1200);

  const topRow = await boxOf('Top', { exact: true, maxX: 300, minY: 150 });
  if (!topRow) return { ok: false, why: 'no-top-datum' };
  await clickAt(topRow.x + topRow.w / 2, topRow.y + topRow.h / 2, 700, 420);
  const sk = await toolBtn('Create new sketch');
  if (!sk) return { ok: false, why: 'no-sketch-tool' };
  await clickAt(sk.x + sk.w / 2, sk.y + sk.h / 2, 1200, 420);
  const plane = await page.evaluate(() => {
    const d = document.querySelector('#feature-dialog');
    if (!d) return null;
    const m = (d.innerText || '').match(/Sketch plane\s*\n?\s*([^\n]*)/);
    return m ? m[1].trim() : null;
  });
  // (no right-click re-orient here: the reload already gives a canonical camera)
  await page.keyboard.press('n'); await P(900);
  await page.keyboard.press('f'); await P(1400);
  await esc(); await P(400);
  return { ok: plane === 'Top plane', plane };
}

// Draw the 100x60 rectangle and commit both dimensions.
async function drawRect100x60() {
  await clickToolBtn('Corner rectangle', { settle: 500 });
  await clickAt(GEO.origin[0], GEO.origin[1], 500, 480);
  await clickAt(GEO.corner2[0], GEO.corner2[1], 1600, 480);
  await page.keyboard.type('100', { delay: 85 }); await P(300);
  await page.keyboard.press('Enter'); await P(900);
  await page.keyboard.type('60', { delay: 85 }); await P(300);
  await page.keyboard.press('Enter'); await P(900);
  await esc(); await P(700);
}

// Draw the d6 hole and dimension it 20 mm from the left and bottom edges.
async function drawHoleDimmed() {
  await clickToolBtn('Center point circle', { settle: 550 });
  await clickAt(GEO.circleC[0], GEO.circleC[1], 650, 500);
  await clickAt(GEO.circleR[0], GEO.circleR[1], 1300, 500);
  await page.keyboard.type('6', { delay: 85 }); await P(320);
  await page.keyboard.press('Enter'); await P(1000);
  await esc(); await P(500);
  // horizontal: left edge -> centre -> place -> 20
  await clickToolBtn('Dimension', { settle: 550 });
  await clickAt(GEO.leftEdge[0], GEO.leftEdge[1], 700, 420);
  await clickAt(GEO.circleC[0], GEO.circleC[1], 750, 400);
  await clickAt(GEO.placeH[0], GEO.placeH[1], 700, 400);
  await page.keyboard.type('20', { delay: 85 }); await P(300);
  await page.keyboard.press('Enter'); await P(900);
  await esc(); await P(450);
  // vertical: bottom edge -> centre -> place -> 20
  await clickToolBtn('Dimension', { settle: 550 });
  await clickAt(GEO.bottomEdge[0], GEO.bottomEdge[1], 700, 420);
  await clickAt(GEO.circleC[0], GEO.circleC[1], 750, 400);
  await clickAt(GEO.placeV[0], GEO.placeV[1], 700, 400);
  await page.keyboard.type('20', { delay: 85 }); await P(300);
  await page.keyboard.press('Enter'); await P(900);
  await esc(); await P(600);
}

async function isFullyDefined() {
  return await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const tips = Array.from(document.querySelectorAll('[data-bs-original-title]')).filter(vis)
      .map((e) => e.getAttribute('data-bs-original-title'));
    return !tips.some((t) => /not fully defined/i.test(t || ''));
  });
}

// Onshape geometry constants, measured from true-resolution captures after
// "select Top datum -> Sketch -> view-cube Top -> N -> f". Verified deterministic.
const CUBE_TOP = [1830, 118];   // view-cube hotspot that yields the canonical top view
const GEO = {
  origin: [1082, 562],
  corner2: [1441, 803],
  rectL: 1082, rectR: 1700, rectT: 562, rectB: 933,
  scale: 6.18,
  circleC: [1206, 809],
  circleR: [1231, 809],
  leftEdge: [1082, 809],
  bottomEdge: [1206, 933],
  placeH: [1140, 752],
  placeV: [1268, 878],
};

// Reload the current document. This restores Onshape's default camera, which
// keeps every take's starting orientation canonical (and the sketch upright).
async function reloadDocument(waitMs = 7000) {
  const url = page.url();
  if (!/\/e\//.test(url)) return { ok: false, why: 'not-in-document' };
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await P(waitMs);
  for (let i = 0; i < 25; i++) { const u = page.url(); await P(400); if (page.url() === u) break; }
  await P(2500);
  await esc(); await P(300);
  return { ok: true, url: page.url() };
}

// Create a new Onshape document with the given name and wait for its Part
// Studio. Used by the tip videos so each one works in a document named after
// itself (the title bar is on screen the whole time).
async function createDocument(name) {
  await page.goto('https://cad.onshape.com/documents', { waitUntil: 'domcontentloaded' });
  await P(2500);
  for (let i = 0; i < 20; i++) { const u = page.url(); await P(320); if (page.url() === u) break; }

  // Poll for the Create button: the SPA renders after the URL settles.
  let createB = null;
  for (let i = 0; i < 40; i++) {
    createB = await boxOf('Create', { exact: true, maxY: 120 });
    if (createB) break;
    await P(500);
  }
  if (!createB) return { ok: false, why: 'no-create-button', url: page.url() };
  await clickAt(createB.x + createB.w / 2, createB.y + createB.h / 2, 600, 400);

  const docItem = await boxOf('Document…', { exact: true, maxY: 560 });
  if (!docItem) return { ok: false, why: 'no-document-item' };
  await clickAt(docItem.x + docItem.w / 2, docItem.y + docItem.h / 2, 1400, 200);

  // Clear the default name through the native setter (Meta+A does not work here).
  await page.evaluate((n) => {
    const el = document.querySelector('.modal input.form-control');
    if (!el) return;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(el, n);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, name);
  await P(400);

  const ok = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const b = Array.from(document.querySelectorAll('.modal button')).filter(vis)
      .find((e) => /^create$/i.test((e.innerText || '').trim()));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  if (!ok) return { ok: false, why: 'no-create-confirm' };
  await clickAt(ok.x + ok.w / 2, ok.y + ok.h / 2, 2000, 500);
  for (let i = 0; i < 40; i++) { await P(500); if (/\/e\//.test(page.url())) break; }
  await P(2500);

  // A new document opens on its tab list; the sketch lives in a Part Studio.
  if (!/\/e\//.test(page.url())) {
    for (let i = 0; i < 20; i++) {
      const tab = await boxOf('Part Studio 1', { exact: false, minY: 1000 });
      if (tab) {
        await clickAt(tab.x + tab.w / 2, tab.y + tab.h / 2, 1800, 400);
        break;
      }
      await P(500);
    }
    for (let i = 0; i < 40; i++) { await P(500); if (/\/e\//.test(page.url())) break; }
    await P(2500);
  }
  return { ok: /\/e\//.test(page.url()), url: page.url() };
}
