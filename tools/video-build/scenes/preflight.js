// PRE-FLIGHT (recorder stopped):
// force a true 1920x1080 compositor surface, trap window.open, install the DOM
// cursor, and hide the Browser Control badge. Retries until the surface is
// genuinely 1920x1080 (navigations and SPA redirects can reset the override).
await page.evaluate(() => { window.open = (u) => { location.href = u; return null; }; });

const cdp = await context.newCDPSession(page);
let surface = null;
for (let i = 0; i < 6; i++) {
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false,
    screenWidth: 1920, screenHeight: 1080,
    screenOrientation: { type: 'landscapePrimary', angle: 0 },
  });
  await P(500);
  // Let any pending SPA navigation settle.
  for (let k = 0; k < 8; k++) { const u = page.url(); await P(320); if (page.url() === u) break; }
  const s = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const b = Buffer.from(s.data, 'base64');
  surface = [b.readUInt32BE(16), b.readUInt32BE(20)];
  if (surface[0] === 1920 && surface[1] === 1080) break;
}

await cursorInject();
await hideBadge();
await P(400);
await hideBadge();

return {
  surface,
  inner: await page.evaluate(() => [innerWidth, innerHeight, devicePixelRatio]),
  url: page.url(),
  ok: surface[0] === 1920 && surface[1] === 1080,
};
