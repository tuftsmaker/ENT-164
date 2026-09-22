// SETUP for take03: completely clear the studio, then create a TOP sketch and
// set the standard framing with an EMPTY canvas (no leftover geometry).
await esc(); await P(300);

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

// Delete every sketch (repeat until none remain) so the canvas is blank.
for (let round = 0; round < 3; round++) {
  await cleanStudio();
  const left = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    return Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
      .map((e) => (e.innerText || '').trim()).filter((t) => /^Sketch \d+$/.test(t)).length;
  });
  if (left === 0) break;
}

const r = await newTopSketchFramed();
const tree = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  return Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
    .map((e) => (e.innerText || '').trim()).filter(Boolean);
});
return { ...r, tree,
  sketches: tree.filter((t) => /^Sketch/.test(t)).length,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
