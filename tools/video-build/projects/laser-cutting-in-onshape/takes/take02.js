// TAKE 02 — s03_partstudio + s04_sketch + s05_normal.
// Part Studio tour, then create a sketch on the TOP plane (datum selected
// first, which is what actually assigns the plane), then press N.
const SIDS = ['s03_partstudio', 's04_sketch', 's05_normal'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take02');
await scenePrep();

const topRow = await boxOf('Top', { exact: true, maxX: 300, minY: 150 });
const f = (o) => (o ? [o.x + o.w / 2, o.y + o.h / 2] : null);

// ---- s03: Part Studio tour ---------------------------------------------
// "The list on the left is the feature list." — point at it.
await B.at(at(O, 's03_partstudio', 2) + 0.4); await moveTo(150, 300, 1200);
B.mark('to-feature-list');
await B.at(at(O, 's03_partstudio', 3) + 0.4); await moveTo(120, 236, 900);
B.mark('origin-row');
await B.at(at(O, 's03_partstudio', 3) + 2.4); if (topRow) await moveTo(...f(topRow), 900);
B.mark('top-row-hover');

// "In the middle is your 3D workspace." — orbit horizontally so the planes
// read as 3D and the orientation cube turns, without tipping past the pole
// (a vertical drag would roll the camera and flip the later sketch view).
await B.at(at(O, 's03_partstudio', 4) + 0.3);
await orbit(1520, 430, 1230, 430, 1400);
B.mark('orbit-1');

// "Every part starts life as a sketch: a two-dimensional drawing on a flat
//  plane." — highlight the Top plane, then orbit back the other way.
await B.at(at(O, 's03_partstudio', 5) + 0.2);
if (topRow) await moveTo(...f(topRow), 800);
B.mark('top-row-hover-2');
await B.at(at(O, 's03_partstudio', 5) + 1.3);
await orbit(1230, 430, 1520, 430, 1400);
B.mark('orbit-2');

// ---- s04: choose the Top plane, then the Sketch tool --------------------
// Normalise the camera first: after orbiting, zoom-to-fit restores the
// canonical orientation so the new sketch views upright.
await B.at(at(O, 's04_sketch', 0) + 0.05);
await page.keyboard.press('f');
await P(1100);

// The datum must be selected BEFORE the Sketch tool for the plane to stick.
await B.at(at(O, 's04_sketch', 0) + 0.7);
if (topRow) await moveTo(...f(topRow), 1100);
B.mark('top-hover');
await B.at(at(O, 's04_sketch', 0) + 1.8);
if (topRow) await clickAt(...f(topRow), 800, 380);
B.mark('top-selected');
await B.at(at(O, 's04_sketch', 0) + 3.0);
const sk = await toolBtn('Create new sketch');
if (sk) await moveTo(sk.x + sk.w / 2, sk.y + sk.h / 2, 900);
B.mark('sketch-hover');
await B.at(at(O, 's04_sketch', 0) + 4.1);
if (sk) await clickAt(sk.x + sk.w / 2, sk.y + sk.h / 2, 900, 240);
B.mark('sketch-clicked');
const planeTxt = await page.evaluate(() => {
  const d = document.querySelector('#feature-dialog');
  if (!d) return null;
  const m = (d.innerText || '').match(/Sketch plane\s*\n?\s*([^\n]*)/);
  return m ? m[1].trim() : null;
});

// "For laser-cut parts, the Top plane is a good habit." -> hover the datum.
await B.at(at(O, 's04_sketch', 1) + 0.4);
if (topRow) await moveTo(...f(topRow), 900);
// "Pick Top, and confirm with the green check mark."
await B.at(at(O, 's04_sketch', 3) + 0.4);
const ok = await page.evaluate(() => {
  const el = document.querySelector('#feature-dialog .ns-dialog-button-ok');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return (r.width > 0 && r.height > 0) ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
});
if (ok) {
  await moveTo(ok.x + ok.w / 2, ok.y + ok.h / 2, 800);
  B.mark('check-hover');
}
// NOTE: the green check commits/CLOSES the sketch and the next scene still has
// to draw in it, so it is only highlighted here; s09 clicks it.
await B.at(at(O, 's04_sketch', 3) + 2.0); await moveTo(1000, 640, 900);

// ---- s05: N for normal view --------------------------------------------
await B.at(at(O, 's05_normal', 0) + 0.3); await moveTo(980, 640, 1100);
await B.at(at(O, 's05_normal', 1) + 0.4);
await page.keyboard.press('n');
B.mark('pressed-N');
await B.at(TOTAL - 0.15);

return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), planeTxt,
  found: { topRow: !!topRow, sk: !!sk, ok: !!ok } };
