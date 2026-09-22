// TAKE 03 — s06_rectangle + s07_dimensions.
// Draw the rectangle and drive it with real numbers.
const SIDS = ['s06_rectangle', 's07_dimensions'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take03');
await scenePrep();

const WIDTH_DIM = [1390, 602];     // the "100" dimension line (measured)
const HEIGHT_DIM = [1661, 748];    // the "60" dimension line (measured)

// ---- s06: pick the rectangle tool and draw ------------------------------
await B.at(at(O, 's06_rectangle', 0) + 0.4);
const rb = await toolBtn('Corner rectangle');
if (rb) await moveTo(rb.x + rb.w / 2, rb.y + rb.h / 2, 900);
B.mark('rect-hover');
await B.at(at(O, 's06_rectangle', 0) + 2.0);
if (rb) await clickAt(rb.x + rb.w / 2, rb.y + rb.h / 2, 600, 240);
B.mark('rect-tool');

// "Click once to set the first corner, then click again for the opposite corner."
await B.at(at(O, 's06_rectangle', 1) + 1.6);
await clickAt(GEO.origin[0], GEO.origin[1], 650, 900);
B.mark('corner1');
await B.at(at(O, 's06_rectangle', 1) + 5.1);
await clickAt(GEO.corner2[0], GEO.corner2[1], 1100, 900);
B.mark('corner2');

// "Onshape adds dimensions as you draw."
await B.at(at(O, 's06_rectangle', 2) + 0.5); await moveTo(WIDTH_DIM[0], WIDTH_DIM[1] - 25, 900);
B.mark('hover-dims');

// ---- s07: dimension it --------------------------------------------------
// "This is the most important habit in the whole tutorial."
// "Never accept a random size."
await B.at(at(O, 's07_dimensions', 1) + 0.4);
await moveTo(WIDTH_DIM[0], WIDTH_DIM[1], 850);
B.mark('width-dim-hover');

// "Click the horizontal dimension and type the real number: one hundred millimetres."
// (After drawing, the width editor is already focused, so typing commits it.)
await B.at(at(O, 's07_dimensions', 2) + 0.6);
await moveTo(WIDTH_DIM[0], WIDTH_DIM[1], 400);
B.mark('width-dim-aim');
await B.at(at(O, 's07_dimensions', 2) + 1.4);
await page.keyboard.type('100', { delay: 135 });
B.mark('typed-100');
// "Then tab to the vertical dimension and type sixty."
await B.at(at(O, 's07_dimensions', 2) + 5.2);
await page.keyboard.press('Enter');
B.mark('committed-100');
await B.at(at(O, 's07_dimensions', 3) + 0.4);
await moveTo(HEIGHT_DIM[0], HEIGHT_DIM[1], 600);
await B.at(at(O, 's07_dimensions', 3) + 1.2);
await page.keyboard.type('60', { delay: 135 });
B.mark('typed-60');
// "Press Enter."
await B.at(at(O, 's07_dimensions', 4) + 0.2);
await page.keyboard.press('Enter');
B.mark('committed-60');
// "Onshape rebuilds the shape to match exactly what you typed."
await B.at(at(O, 's07_dimensions', 5) + 2.4); await moveTo(1500, 700, 1200);
await B.at(TOTAL - 0.15);
await esc();
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), found: { rb: !!rb } };
