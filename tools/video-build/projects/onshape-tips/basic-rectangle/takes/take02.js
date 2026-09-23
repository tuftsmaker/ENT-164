// TAKE 02 — exporting the sketch. The setup leaves the finished rectangle with
// the sketch committed, because you export the feature, not an open sketch.
const SIDS = ['s02'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take02');
await scenePrep();

// "Once the sketch is done, it has to leave Onshape to reach the laser cutter."
await B.at(at(O, 's02', 0) + 0.4);
await moveTo(1180, 700, 800);
B.mark('the-sketch');

// "Right-click the sketch in the feature list, and choose Export as DXF."
await B.at(at(O, 's02', 1) + 0.3);
const row = await boxOf('Sketch 1', { exact: true, maxX: 300, minY: 200 });
if (row) await rightClickAt(row.x + row.w / 2, row.y + row.h / 2, 700, 500);
B.mark('context-menu');
await P(250);
const item = await boxOf('Export as DXF', { exact: false });
if (item) await clickAt(item.x + item.w / 2, item.y + item.h / 2, 900, 450);
B.mark('export-item');

// "DXF is exactly what the cutter wants: the two-dimensional lines, and nothing
//  else."
await B.at(at(O, 's02', 2) + 0.5);
await moveTo(940, 430, 800);          // the dialog: format, version, units
B.mark('dialog');
await B.at(at(O, 's02', 2) + 3.6);
await moveTo(1000, 560, 700);
B.mark('units');

// "Pick a folder you'll find again, and save the file."
await B.at(at(O, 's02', 3) + 0.4);
const exp = await boxOf('Export', { exact: true });
if (exp) await clickAt(exp.x + exp.w / 2, exp.y + exp.h / 2, 1200, 500);
B.mark('exported');

// "That's the file you open in Inkscape, or hand straight to the laser cutter."
await B.at(at(O, 's02', 4) + 0.3);
await moveTo(1500, 420, 800);
B.mark('saved');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => ({
  dialogOpen: !!document.querySelector('.modal, [role=dialog], .os-dialog'),
  features: Array.from(document.querySelectorAll('.os-list-item-name'))
    .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 5),
}));
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
