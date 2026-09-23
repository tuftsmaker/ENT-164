// SETUP: the finished rectangle, with the sketch committed so it appears in the
// feature list - exporting works on the feature, not on an open sketch.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'A Basic Rectangle as My First Sketch' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
const sk = await newTopSketchFramed();
if (!sk.ok) return { step: 'no-top-sketch', sk };
await drawRect100x60();

// Commit and close the sketch: the green check in the sketch dialog.
async function commitSketch() {
  const b = await page.evaluate(() => {
    const el = document.querySelector('#feature-dialog .ns-dialog-button-ok');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return (r.width > 0 && r.height > 0) ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
  });
  if (!b) return false;
  await clickAt(b.x + b.w / 2, b.y + b.h / 2, 900, 460);
  return true;
}
const committed = await commitSketch();
await P(900);

const features = await page.evaluate(() => Array.from(document.querySelectorAll('.os-list-item-name'))
  .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 4));
return { step: 'ready', doc: cfg.documentName, committed, features,
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
