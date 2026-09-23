// SETUP: a clean Part Studio with the default isometric camera, so the three
// planes are on screen for the tour. Nothing is drawn.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'Workspace Overview' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();
await esc(); await P(300);
await page.keyboard.press('f'); await P(1200);       // zoom to fit the empty studio
await esc(); await P(250);

return { step: 'ready', doc: cfg.documentName,
  openSketchDialog: await page.evaluate(
    () => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')) };
