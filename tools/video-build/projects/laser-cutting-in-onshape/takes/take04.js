// TAKE 04 — s08_circle + s09_finish.
// Add the d6 hole at an approximate spot, then position it accurately.
const SIDS = ['s08_circle', 's09_finish'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take04');
await scenePrep();

const C = (i) => at(O, 's08_circle', i);
const F = (i) => at(O, 's09_finish', i);

// ---- s08 ----------------------------------------------------------------
// "Most laser-cut parts need a hole." (nothing to click yet)

// "Pick the Circle tool, or press C, and click the approximate location of
//  where the hole goes."
await B.at(C(1) + 0.4);
const cb = await toolBtn('Center point circle');
if (cb) await moveTo(cb.x + cb.w / 2, cb.y + cb.h / 2, 900);
B.mark('circle-hover');
await B.at(C(1) + 1.6);
if (cb) await clickAt(cb.x + cb.w / 2, cb.y + cb.h / 2, 500, 240);
B.mark('circle-tool');
await B.at(C(1) + 3.5);
await clickAt(GEO.circleC[0], GEO.circleC[1], 650, 1000);
B.mark('centre');
await B.at(C(1) + 4.8);
await clickAt(GEO.circleR[0], GEO.circleR[1], 700, 800);
B.mark('radius');

// "We'll position it accurately next."
await B.at(C(2) + 0.2);
await page.keyboard.type('6', { delay: 130 });
B.mark('typed-6');
await B.at(C(2) + 1.2);
await page.keyboard.press('Enter');
B.mark('committed-6');
await esc(); await P(400);

// "Here's how."
await B.at(C(3) + 0.2);
const db = await toolBtn('Dimension');
if (db) await moveTo(db.x + db.w / 2, db.y + db.h / 2, 800);
B.mark('dim-hover');
await B.at(C(3) + 0.8);
if (db) await clickAt(db.x + db.w / 2, db.y + db.h / 2, 380, 200);
B.mark('dim-tool');

// "Dimension the circle to the diameter of your bolt, and dimension its
//  position from the edges."
await B.at(C(4) + 0.5);
await clickAt(GEO.leftEdge[0], GEO.leftEdge[1], 600, 900);
B.mark('left-edge');
await B.at(C(4) + 1.0);
await clickAt(GEO.circleC[0], GEO.circleC[1], 600, 260);
B.mark('centre-for-h');
await B.at(C(4) + 1.5);
await clickAt(GEO.placeH[0], GEO.placeH[1], 600, 300);
B.mark('h-placed');
await B.at(C(4) + 2.0);
await page.keyboard.type('20', { delay: 130 });
await B.at(C(4) + 3.0);
await page.keyboard.press('Enter');
B.mark('h-committed');
await esc(); await P(400);

// "Same habit: type real numbers."
await B.at(C(5) + 0.2);
if (db) await clickAt(db.x + db.w / 2, db.y + db.h / 2, 360, 200);
await B.at(C(5) + 0.9);
await clickAt(GEO.bottomEdge[0], GEO.bottomEdge[1], 560, 280);
B.mark('bottom-edge');
await B.at(C(5) + 1.4);
await clickAt(GEO.circleC[0], GEO.circleC[1], 560, 250);
B.mark('centre-for-v');
await B.at(C(5) + 1.9);
await clickAt(GEO.placeV[0], GEO.placeV[1], 560, 280);
B.mark('v-placed');
// "If you measured six millimetres, type six."
await B.at(C(6) + 0.3);
await page.keyboard.type('20', { delay: 130 });
await B.at(C(6) + 1.4);
await page.keyboard.press('Enter');
B.mark('v-committed');
await esc(); await P(500);
const fully = await isFullyDefined();

// ---- s09: fully constrained -> green check ------------------------------

// "Click the green check to close the sketch."
await B.at(F(2) + 0.8);
const ok = await page.evaluate(() => {
  const el = document.querySelector('#feature-dialog .ns-dialog-button-ok');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return (r.width > 0 && r.height > 0) ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
});
if (ok) {
  await moveTo(ok.x + ok.w / 2, ok.y + ok.h / 2, 820);
  B.mark('check-hover');
  await P(340);
  await clickAt(ok.x + ok.w / 2, ok.y + ok.h / 2, 1100, 220);
  B.mark('check-clicked');
}

// "Your drawing is stored in the feature list, and you can reopen it at any time."
await B.at(F(3) + 0.5);
const row = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const hit = Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
    .find((e) => /^Sketch \d+$/.test((e.innerText || '').trim()) && e.getBoundingClientRect().x < 300);
  if (!hit) return null;
  const r = hit.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
if (row) await moveTo(row.x + row.w / 2, row.y + row.h / 2, 950);
B.mark('hover-feature');
await B.at(F(3) + 3.0); await moveTo(900, 600, 1100);
await B.at(TOTAL - 0.15);
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), fully,
  found: { cb: !!cb, db: !!db, ok: !!ok, row: !!row } };
