// No-op setup: the state is already prepared by a previous script.
return { step: 'noop', url: page.url(),
  sketchOpen: await page.evaluate(() => !!document.querySelector('#feature-dialog .ns-dialog-button-ok')),
  tree: await page.evaluate(() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    return Array.from(document.querySelectorAll('.os-list-item-name')).filter(vis)
      .map((e) => (e.innerText || '').trim()).filter(Boolean);
  }) };
