// SETUP: land on a fully-settled documents page.
await esc();
await P(300);
await page.goto('https://cad.onshape.com/documents', { waitUntil: 'domcontentloaded' });
await P(3000);

let stable = 0, last = '';
for (let i = 0; i < 60; i++) {
  const u = page.url();
  const hasCreate = await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    return Array.from(document.querySelectorAll('button')).filter(vis)
      .some((e) => /^create$/i.test((e.innerText || '').trim()));
  }).catch(() => false);
  if (u === last && hasCreate) { stable++; if (stable >= 3) break; } else { stable = 0; }
  last = u;
  await P(500);
}

const cancel = await page.evaluate(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const b = Array.from(document.querySelectorAll('.modal button')).filter(vis)
    .find((e) => /^cancel$/i.test((e.innerText || '').trim()));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
if (cancel) await clickAt(cancel.x + cancel.w / 2, cancel.y + cancel.h / 2, 800, 260);
await page.evaluate(() => window.scrollTo(0, 0));
await P(1000);
return { url: page.url(), stable };
