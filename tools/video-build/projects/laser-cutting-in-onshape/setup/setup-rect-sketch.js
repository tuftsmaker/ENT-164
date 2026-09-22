// SETUP for take04: ensure a framed TOP sketch is open, then draw the
// 100x60 rectangle. If a suitable sketch is already open we reuse it, which
// avoids exiting/re-entering the sketch (that flips the camera roll).
if (!/\/e\//.test(page.url())) {
  await page.goto('https://cad.onshape.com/documents', { waitUntil: 'domcontentloaded' });
  await P(3500);
  for (let i = 0; i < 20; i++) { const u = page.url(); await P(320); if (page.url() === u) break; }
  const row = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const rows = Array.from(document.querySelectorAll('.document-list-item-name')).filter(vis);
    const hit = rows.find((e) => /Laser Cut Bracket/i.test(e.innerText || ''));
    if (!hit) return null;
    const r = hit.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  if (!row) return { step: 'no-bracket-doc', url: page.url() };
  await page.mouse.move(row.x + row.w / 2, row.y + row.h / 2, { steps: 4 });
  await P(250);
  await page.mouse.down(); await P(60); await page.mouse.up();
  for (let i = 0; i < 60; i++) { await P(500); if (/\/e\//.test(page.url())) break; }
  await P(3500);
}

await reloadDocument();

// Is a framed Top sketch already open with nothing drawn?
const probe = await page.evaluate(() => {
  const d = document.querySelector('#feature-dialog');
  const open = !!d && (() => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; })();
  const m = d ? (d.innerText || '').match(/Sketch plane\s*\n?\s*([^\n]*)/) : null;
  return { open, plane: m ? m[1].trim() : null };
});

let created = null;
if (!(probe.open && probe.plane === 'Top plane')) {
  await cleanStudio();
  created = await newTopSketchFramed();
  if (!created.ok) return { step: 'no-top-sketch', created };
}

await drawRect100x60();
const fully = await isFullyDefined();
return { step: 'ready', reused: !created, plane: probe.plane || (created && created.plane), fully,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
