// SETUP: a finger-and-slot joint, drawn off-camera. Two closed polylines - a
// panel with a notch in its top edge, and a strip with a finger that drops into
// it - plus the one dimension the whole joint depends on: the slot width, at
// the material thickness.
//
// Drawn as polylines rather than rectangles plus trims: a notch is a bite out
// of an edge, and tracing the outline directly avoids four trim operations per
// corner and the separate loose rectangle a straddling rectangle would leave.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'Creating Laser Cut Joints' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };

const MM = GEO.scale;                 // px per mm (6.18)
const T = Math.round(3 * MM);         // the slot, at the material thickness

// The panel: 40 x 25 mm, with a 3mm notch, 10mm deep, in its top edge.
const PX = 1100, PY = 660, PW = Math.round(40 * MM), PH = Math.round(25 * MM);
const NX0 = PX + 114, NX1 = NX0 + T, NY = PY + Math.round(10 * MM);

await clickToolBtn('Line', { settle: 400 });
for (const [x, y] of [
  [PX, PY], [NX0, PY], [NX0, NY], [NX1, NY], [NX1, PY],
  [PX + PW, PY], [PX + PW, PY + PH], [PX, PY + PH], [PX, PY],
]) await clickAt(x, y, 240, 280);
await esc(); await P(350);

// The mating strip: 25 x 5 mm, with a finger that drops into the notch and
// stops a little short of its floor, so the two pieces read as separate parts.
const SW = Math.round(25 * MM), SH = Math.round(5 * MM);
const SX = PX + 45, SY = PY - SH - 19;
const FY = NY - 12;

await clickToolBtn('Line', { settle: 400 });
for (const [x, y] of [
  [SX, SY], [SX + SW, SY], [SX + SW, SY + SH], [NX1, SY + SH],
  [NX1, FY], [NX0, FY], [NX0, SY + SH], [SX, SY + SH], [SX, SY],
]) await clickAt(x, y, 240, 280);
await esc(); await P(350);

// The number the joint depends on: the slot width.
await clickToolBtn('Dimension', { settle: 450 });
await clickAt(Math.round((NX0 + NX1) / 2), NY, 420, 420);
await clickAt(Math.round((NX0 + NX1) / 2), NY + 46, 420, 420);
await page.keyboard.type('3', { delay: 90 }); await P(280);
await page.keyboard.press('Enter'); await P(700);
await esc(); await P(300);

return { step: 'ready', doc: cfg.documentName, plane: sk.plane,
  slotPx: T, dimAt: [Math.round((NX0 + NX1) / 2), NY + 46] };
