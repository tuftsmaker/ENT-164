// SETUP: a clean Part Studio with the default isometric camera. Nothing is
// drawn: this video shows the whole flow on camera, from choosing the plane to
// typing the rectangle's dimensions.
const cfg = (() => {
  try {
    const ptr = JSON.parse(_fs.readFileSync('/tmp/vid/vb-paths.json', 'utf8'));
    return JSON.parse(_fs.readFileSync(ptr.project + '/video.json', 'utf8'));
  } catch (e) { return { documentName: 'A Basic Rectangle as My First Sketch' }; }
})();

const made = cfg.documentUrl ? await openDocument(cfg.documentUrl) : await createDocument(cfg.documentName);
if (!made.ok) return { step: 'could-not-open-document', made };

await cleanStudio();          // any leftover sketch from a previous take
await esc(); await P(300);
await page.keyboard.press('f'); await P(1200);       // zoom to fit the empty studio
await esc(); await P(250);

const openSketchDialog = await page.evaluate(
  () => !!document.querySelector('#feature-dialog .ns-dialog-button-ok'));
return { step: 'ready', doc: cfg.documentName, openSketchDialog,
  plane: await page.evaluate(() => {
    const d = document.querySelector('#feature-dialog');
    return d ? (d.innerText || '').replace(/\n+/g, ' ').slice(0, 60) : null;
  }) };
