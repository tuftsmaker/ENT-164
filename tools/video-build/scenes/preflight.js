// PRE-FLIGHT (recorder stopped):
// force a true 1920x1080 compositor surface, trap window.open, install the DOM
// cursor, and hide the Browser Control badge. The surface is pinned again here
// because a navigation since the setup may have reset the override.
await page.evaluate(() => { window.open = (u) => { location.href = u; return null; }; });

const surface = await pinSurface();

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
