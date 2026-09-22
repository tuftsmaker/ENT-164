// Shared helpers for the Onshape demo scenes.
// Injected into every execute() call via a small prelude.

const P = (ms) => page.waitForTimeout(ms);

async function m(x, y, steps = 1) {
  await page.mouse.move(x, y, { steps });
}

async function hover(x, y, ms = 250) {
  await page.mouse.move(x, y, { steps: 8 });
  await page.waitForTimeout(ms);
}

async function click(x, y, sel = 1) {
  await page.mouse.move(x, y, { steps: 6 });
  await page.waitForTimeout(140);
  await page.mouse.down({ button: 'left', clickCount: sel });
  await page.mouse.up({ button: 'left', clickCount: sel });
}

async function clickSel(x, y) {
  await click(x, y, 1);
}

async function dbl(x, y) {
  await page.mouse.move(x, y, { steps: 6 });
  await page.waitForTimeout(140);
  await page.mouse.down({ button: 'left', clickCount: 1 });
  await page.mouse.up({ button: 'left', clickCount: 1 });
  await page.waitForTimeout(70);
  await page.mouse.down({ button: 'left', clickCount: 2 });
  await page.mouse.up({ button: 'left', clickCount: 2 });
}

async function esc() {
  await page.keyboard.press('Escape');
  await page.waitForTimeout(250);
}

const TOOL = (title) => `[data-bs-original-title=${JSON.stringify(title)}]`;

async function toolBox(title) {
  const el = await page.evaluateHandle(
    (t) => Array.from(document.querySelectorAll('[data-bs-original-title]'))
      .find((e) => e.getAttribute('data-bs-original-title') === t),
    title
  );
  const handle = el.asElement();
  if (!handle) throw new Error('tool not found: ' + title);
  return await handle.boundingBox();
}

async function clickTool(title) {
  const b = await toolBox(title);
  const cx = b.x + b.width / 2;
  const cy = b.y + b.height / 2;
  await page.mouse.move(cx, cy, { steps: 10 });
  await page.waitForTimeout(420);
  await page.mouse.down({ button: 'left', clickCount: 1 });
  await page.mouse.up({ button: 'left', clickCount: 1 });
  await page.waitForTimeout(500);
  return { cx, cy };
}

async function bodyText() {
  return await page.locator('body').innerText();
}

async function shot(name) {
  const dir = process.env.SCENE_DIR || '/tmp/vid/frames';
  await page.screenshot({ path: `${dir}/${name}.png` });
}

// Visible text inputs anywhere in the page (Onshape puts dimension editors in the DOM).
async function inputs() {
  return await page.evaluate(() => Array.from(
    document.querySelectorAll('input:not([type=hidden]), textarea, [contenteditable="true"]')
  ).filter((e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }).map((e) => {
    const r = e.getBoundingClientRect();
    return {
      tag: e.tagName,
      cls: String(e.className).slice(0, 70),
      val: e.value ?? e.textContent,
      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    };
  }));
}

module.exports = { P, m, hover, click, clickSel, dbl, esc, clickTool, toolBox, bodyText, shot, inputs };
