// SETUP for take05: open a Part Studio, build the finished fully-constrained
// sketch on TOP, close it, and frame the view. All off-camera.
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
await cleanStudio();

const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };
await drawRect100x60();
await drawHoleDimmed();
const fully = await isFullyDefined();

// Close the sketch with the green check.
const ok = await page.evaluate(() => {
  const el = document.querySelector('#feature-dialog .ns-dialog-button-ok');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return (r.width > 0 && r.height > 0) ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
});
if (ok) await clickAt(ok.x + ok.w / 2, ok.y + ok.h / 2, 1400, 400);
await esc(); await P(500);

// Frame: zoom to the sketch selection, then ease out for margin.
const zoomSel = async () => {
  const row = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const hit = Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
      .find((e) => /^Sketch \d+$/.test((e.innerText || '').trim()) && e.getBoundingClientRect().x < 300);
    if (!hit) return null;
    const r = hit.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  if (!row) return false;
  await page.mouse.move(row.x + row.w / 2, row.y + row.h / 2, { steps: 4 });
  await P(300);
  await page.mouse.down({ button: 'right' }); await P(80); await page.mouse.up({ button: 'right' });
  await P(700);
  const item = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const hit = Array.from(document.querySelectorAll('*')).filter(vis)
      .find((e) => (e.innerText || '').trim() === 'Zoom to selection' && e.children.length === 0);
    if (!hit) return null;
    const r = hit.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  if (!item) { await esc(); return false; }
  await page.mouse.move(item.x + item.w / 2, item.y + item.h / 2, { steps: 4 });
  await P(250);
  await page.mouse.down(); await P(70); await page.mouse.up();
  await P(1500);
  await esc(); await P(400);
  await page.mouse.move(1000, 560, { steps: 4 });
  await P(250);
  for (let i = 0; i < 4; i++) { await page.mouse.wheel(0, 240); await P(230); }
  await P(800);
  await esc(); await P(400);
  return true;
};
const framed = await zoomSel();

return { step: 'ready', plane: sk.plane, fully, framed,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
