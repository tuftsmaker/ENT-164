// SETUP: fresh document named after the video, a Top sketch, and a
// dimensioned 100x60 rectangle. All off-camera.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'Combining Shapes with the Trim Tool' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };
await drawRect100x60();
const fully = await isFullyDefined();
return { step: 'ready', doc: cfg.documentName, plane: sk.plane, fully,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
