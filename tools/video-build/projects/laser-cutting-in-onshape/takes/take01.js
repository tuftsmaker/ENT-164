// TAKE 01 — s01_intro + s02_documents. Documents page -> Create -> name it.
// The document is named to match the video title, and the name field is
// cleared explicitly (select-all alone was appending to the default value).
const SIDS = ['s01_intro', 's02_documents'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const DOC_NAME = 'Laser Cutting in Onshape';
const B = Beat(TOTAL, 'take01');
await scenePrep();

const f = (o) => (o ? [o.x + o.w / 2, o.y + o.h / 2] : null);
const rowDoc = await boxOf('ENT-164 Laser Cutting Demo', { exact: false, maxY: 800 });
const createB = await boxOf('Create', { exact: true, maxY: 120 });

// ---- s01: the documents page (one purposeful move, then rest) -----------
await B.at(at(O, 's01_intro', 2) + 1.0);
if (rowDoc) await moveTo(rowDoc.x + 130, rowDoc.y + rowDoc.h / 2, 1100);
B.mark('design-list');

// ---- s02: Create -> Document -> name -----------------------------------
await B.at(O.s02_documents + 8.2);
if (rowDoc) await moveTo(rowDoc.x + 130, rowDoc.y + rowDoc.h / 2, 700);
await B.at(O.s02_documents + 11.6);
if (createB) {
  await moveTo(...f(createB), 700);
  B.mark('create-hover');
  await P(250);
  await clickAt(...f(createB), 520, 130);
  B.mark('create-open');
}
const docItem = await boxOf('Document…', { exact: true, maxY: 560 });
if (docItem) {
  await moveTo(...f(docItem), 560);
  await P(200);
  await clickAt(...f(docItem), 1200, 140);
  B.mark('dialog-open');
}

// Clear the default name properly, then type the real one.
const nameInput = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const c = Array.from(document.querySelectorAll('.modal input.form-control')).filter(vis);
  if (!c.length) return null;
  const r = c[0].getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height, val: c[0].value };
});
let nameFinal = null;
if (nameInput) {
  const cx = nameInput.x + nameInput.w / 2, cy = nameInput.y + nameInput.h / 2;
  await clickAt(cx, cy, 320, 460);
  // Meta+A does not select-all in this field, so clear the default value
  // through the native setter (Angular picks it up), then type it visibly.
  await page.evaluate(() => {
    const el = document.querySelector('.modal input.form-control');
    if (!el) return;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(el, '');
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await P(220);
  await page.keyboard.type(DOC_NAME, { delay: 45 });
  await P(280);
  nameFinal = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const c = Array.from(document.querySelectorAll('.modal input.form-control')).filter(vis);
    return c.length ? c[0].value : null;
  });
  B.mark('named');
}

// Create it -> opens the Part Studio.
await P(500);
const okBtn = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const b = Array.from(document.querySelectorAll('.modal button')).filter(vis)
    .find((e) => /^create$/i.test((e.innerText || '').trim()));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
if (okBtn) {
  await clickAt(okBtn.x + okBtn.w / 2, okBtn.y + okBtn.h / 2, 2000, 600);
  B.mark('created');
}
for (let i = 0; i < 30; i++) { await P(500); if (/\/e\//.test(page.url())) break; }
await P(3500);
B.mark('studio');

return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), url: page.url(),
  docNameTyped: DOC_NAME, nameFinal,
  found: { rowDoc: !!rowDoc, createB: !!createB, docItem: !!docItem, nameInput: !!nameInput, okBtn: !!okBtn } };
