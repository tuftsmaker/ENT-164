// SETUP: fresh document, a Top sketch, a vertical centre line through the
// sketch origin, and the dimensioned 100x60 half with its left edge on it.
// All off-camera.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'Mirroring Entities' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };

// The mirror line, drawn first and running well past the shape at both ends so
// the take can click it clear of the geometry.
await clickToolBtn('Line', { settle: 500 });
await clickAt(GEO.origin[0], GEO.origin[1] - 110, 420, 460);
await clickAt(GEO.origin[0], GEO.origin[1] + 300, 420, 460);
await esc(); await P(400);

await drawRect100x60();
const fully = await isFullyDefined();
return { step: 'ready', doc: cfg.documentName, plane: sk.plane, fully,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
