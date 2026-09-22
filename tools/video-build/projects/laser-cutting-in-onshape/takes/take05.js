// TAKE 05 — s10_dxf + s11_recap.
// All state preparation happens in setup-final-sketch.js, so the beat clock
// starts at the first on-camera action and the visuals stay locked to the
// narration. s10 now defers the Nolop/Inkscape step to a separate video.
const SIDS = ['s10_dxf', 's11_recap'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);

await scenePrep();

const sketchRow = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const hit = Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
    .find((e) => /^Sketch \d+$/.test((e.innerText || '').trim()) && e.getBoundingClientRect().x < 300);
  if (!hit) return null;
  const r = hit.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});

const B = Beat(TOTAL, 'take05');

// "For the laser cutter, you need a DXF file."
await B.at(at(O, 's10_dxf', 0) + 0.4); await moveTo(900, 560, 1200);
await B.at(at(O, 's10_dxf', 0) + 1.9); await moveTo(1120, 660, 1000);

// "Right-click the sketch in the feature list, and choose Export as D X F."
await B.at(at(O, 's10_dxf', 1) + 0.5);
if (sketchRow) {
  await moveTo(sketchRow.x + sketchRow.w / 2, sketchRow.y + sketchRow.h / 2, 900);
  B.mark('row-hover');
  await P(450);
  await rightClickAt(sketchRow.x + sketchRow.w / 2, sketchRow.y + sketchRow.h / 2, 650, 200);
  B.mark('context-menu');
}
const dxfItem = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const hit = Array.from(document.querySelectorAll('*')).filter(vis)
    .find((e) => (e.innerText || '').trim() === 'Export as DXF/DWG\u2026' && e.children.length === 0);
  if (!hit) return null;
  const r = hit.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
if (dxfItem) {
  await B.at(at(O, 's10_dxf', 1) + 2.6);
  await moveTo(dxfItem.x + dxfItem.w / 2, dxfItem.y + dxfItem.h / 2, 800);
  B.mark('dxf-hover');
  await B.at(at(O, 's10_dxf', 1) + 3.9);
  await clickAt(dxfItem.x + dxfItem.w / 2, dxfItem.y + dxfItem.h / 2, 1200, 200);
  B.mark('dxf-dialog');
}

// "Save it, and take it to Nolop, where it gets imported in Inkscape."
await B.at(at(O, 's10_dxf', 2) + 0.3);
const exportBtn = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const b = Array.from(document.querySelectorAll('.modal button.btn-primary')).filter(vis)
    .find((e) => /^export$/i.test((e.innerText || '').trim()));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
if (exportBtn) {
  await B.at(at(O, 's10_dxf', 2) + 0.6);
  await moveTo(exportBtn.x + exportBtn.w / 2, exportBtn.y + exportBtn.h / 2, 800);
  B.mark('export-hover');
  await B.at(at(O, 's10_dxf', 2) + 1.8);
  await clickAt(exportBtn.x + exportBtn.w / 2, exportBtn.y + exportBtn.h / 2, 1500, 200);
  B.mark('exported');
}

// The remaining lines describe the laser side, which this video does not show,
// so the picture simply holds on the exported file.
await B.at(TOTAL - 0.15);
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(),
  found: { sketchRow: !!sketchRow, dxfItem: !!dxfItem, exportBtn: !!exportBtn } };
