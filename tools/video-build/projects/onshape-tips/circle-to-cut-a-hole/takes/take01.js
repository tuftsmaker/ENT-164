// TAKE 01 — Adding a Circle to a Rectangle to Cut a Hole.
// The setup leaves the dimensioned rectangle's sketch open; we pick the circle
// tool and draw the hole in it.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const REST = [1300, 700];   // on the rectangle, out of the way of the toolbar

// "Next, I'm going to show you how to add a hole to cut in our rectangle."
await B.at(at(O, 's01', 0) + 0.5);
await moveTo(REST[0], REST[1], 900);
B.mark('showing-rectangle');

// "Say we want to cut a hole; the simplest way is with the circle tool."
// Park the cursor on the tool before clicking it, so the click is telegraphed.
const ct = await toolBtn('Center point circle');
await B.at(at(O, 's01', 1) + 0.5);
if (ct) await moveTo(ct.x + ct.w / 2, ct.y + ct.h / 2, 850);
B.mark('hover-circle-tool');

// "So I'll pick the circle tool, and then we can draw a circle anywhere we
//  want to cut the hole."
await B.at(at(O, 's01', 2) + 0.3);
await clickToolBtn('Center point circle', { settle: 600 });
B.mark('picked-circle-tool');

await B.at(at(O, 's01', 2) + 3.4);
await clickAt(GEO.circleC[0], GEO.circleC[1], 650, 500);   // centre
B.mark('circle-centre');

await B.at(at(O, 's01', 2) + 4.7);
await clickAt(GEO.circleR[0], GEO.circleR[1], 1000, 500);  // radius
B.mark('circle-drawn');

// "There we go, we have a circle."
await B.at(at(O, 's01', 3) + 0.3);
await esc();                                               // end the circle tool
await P(350);
await moveTo(GEO.circleC[0] + 95, GEO.circleC[1] + 95, 750);
B.mark('circle-done');

// "If we sent this to the laser cutter, it would cut out the square, and then
//  it would cut a hole in the middle, and you'd have a square with a hole in it."
// Trace the hole, then settle back on the part.
await B.at(at(O, 's01', 4) + 1.0);
await moveTo(GEO.circleC[0] + 52, GEO.circleC[1] - 6, 800);   // onto the circle
B.mark('hole-highlighted');

await B.at(at(O, 's01', 4) + 4.6);
await moveTo(GEO.circleC[0] - 70, GEO.circleC[1] + 150, 900); // back onto the square
B.mark('showing-square');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => ({
  features: Array.from(document.querySelectorAll('.os-list-item-name'))
    .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 5),
}));
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
