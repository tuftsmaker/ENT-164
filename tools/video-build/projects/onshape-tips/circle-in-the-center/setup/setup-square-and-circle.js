// SETUP: a dimensioned 100x60 rectangle with one stray circle in it - the one
// the video starts by deleting. All off-camera.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'Placing a Circle in the Center of a Rectangle' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };
await drawRect100x60();

// The stray circle the take deletes first.
await clickToolBtn('Center point circle', { settle: 500 });
await clickAt(GEO.circleC[0], GEO.circleC[1], 600, 520);
await clickAt(GEO.circleC[0] + 30, GEO.circleC[1], 800, 500);
await esc(); await P(400);

const fully = await isFullyDefined();
return { step: 'ready', doc: cfg.documentName, plane: sk.plane, fully,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
