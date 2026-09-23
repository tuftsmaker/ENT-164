// TAKE 01 — Adding a Circle of the Corner of a Square.
// The setup leaves the dimensioned square's sketch open. We run a construction
// line out of a corner, place the circle on it, and dimension it from the edge.
//
// The whole sequence has to be finished by the end of the narration (~19.7s),
// so every settle below is deliberately short.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const MID_Y = Math.round((GEO.rectT + GEO.rectB) / 2);
const CORNER = [GEO.rectR, GEO.rectT];                  // top-right corner of the square
const ALONG = [CORNER[0] - 155, CORNER[1] + 155];       // construction line, 45 degrees in
const CIRC = [CORNER[0] - 82, CORNER[1] + 82];          // circle centre, on that line
const CIRC_R = [CIRC[0] + 27, CIRC[1]];
const PLACE = [CIRC[0] + 40, CIRC[1] - 70];             // where the dimension text goes

// "Now let's look at placing a circle at a corner of the square."
await B.at(at(O, 's01', 0) + 0.4);
await moveTo(1450, 700, 800);
B.mark('the-square');

// "The same idea as centring it, but this time we anchor to a corner instead
//  of a midpoint."
await B.at(at(O, 's01', 1) + 0.2);
await moveTo(CORNER[0] - 20, CORNER[1] + 20, 700);
B.mark('the-corner');

// "I'll draw a construction line out from the corner, then place the circle
//  where those lines meet, and dimension it from the edges."
await B.at(at(O, 's01', 2) + 0.1);
await clickToolBtn('Construction', { settle: 320, moveMs: 400 });
B.mark('construction-on');

await B.at(at(O, 's01', 2) + 1.1);
await clickToolBtn('Line', { settle: 320, moveMs: 400 });
await clickAt(CORNER[0], CORNER[1], 320, 400);
await clickAt(ALONG[0], ALONG[1], 360, 400);
await esc(); await P(220);
await clickToolBtn('Construction', { settle: 300, moveMs: 380 });  // off again: the circle is real geometry
await esc(); await P(200);
B.mark('construction-line');

await B.at(at(O, 's01', 2) + 2.9);
await clickToolBtn('Center point circle', { settle: 340, moveMs: 400 });
await clickAt(CIRC[0], CIRC[1], 360, 420);
await clickAt(CIRC_R[0], CIRC_R[1], 500, 420);
await esc(); await P(220);
B.mark('circle-placed');

// "That gives us a hole at a known distance from the corner, rather than one
//  that just looks about right."
await B.at(at(O, 's01', 3) + 0.1);
await clickToolBtn('Dimension', { settle: 320, moveMs: 400 });
await clickAt(GEO.rectR, MID_Y, 360, 400);              // right edge
await clickAt(CIRC[0], CIRC[1], 360, 400);              // the circle centre
await clickAt(PLACE[0], PLACE[1], 360, 400);            // drop the dimension
await page.keyboard.type('20', { delay: 85 });
await P(250);
await page.keyboard.press('Enter');
await P(600);
await esc(); await P(220);
B.mark('dimensioned');
await moveTo(CIRC[0] + 70, CIRC[1] + 70, 700);
B.mark('hole-placed');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => ({
  features: Array.from(document.querySelectorAll('.os-list-item-name'))
    .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 5),
}));
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
