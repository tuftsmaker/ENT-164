// TAKE 01 — Mirroring Entities.
// The setup leaves a centre line and one dimensioned half drawn. We mirror the
// half across the line, then change a dimension to show both halves follow.
//
// Onshape's sketch Mirror tool has no dialog: it prompts for the MIRROR LINE
// first ("Select a mirror line.") and only then for the entities to mirror.
// Pick them in that order or the picks land in the wrong field.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const MID_Y = Math.round((GEO.rectT + GEO.rectB) / 2);
const LINE = [GEO.origin[0], GEO.origin[1] - 70];     // centre line, above the shape
const HALF = [1400, 760];                             // on the drawn half
const MIRRORED = [GEO.origin[0] - 300, MID_Y];        // where the reflection lands
const WIDTH_DIM = [1390, 602];                        // the "100" dimension line

// "If a part is symmetrical, you only need to draw half of it."
await B.at(at(O, 's01', 0) + 0.4);
await moveTo(HALF[0], HALF[1], 850);
B.mark('half-only');

// "Draw one side, then use the mirror tool to reflect it across a centre line..."
await B.at(at(O, 's01', 1) + 0.2);
await clickToolBtn('Mirror', { settle: 750 });
B.mark('mirror-tool');

await B.at(at(O, 's01', 1) + 1.7);
await clickAt(LINE[0], LINE[1], 800, 620);            // 1. the mirror line
B.mark('mirror-line');

await B.at(at(O, 's01', 1) + 3.3);
await clickAt(1300, GEO.rectT + 1, 550, 500);         // 2. the three edges that
B.mark('edge-top');
await clickAt(GEO.rectR - 1, MID_Y + 3, 550, 500);    //    are not on the line
B.mark('edge-right');

// "...and Onshape creates the other half for you."
await B.at(at(O, 's01', 1) + 5.0);
await clickAt(1300, GEO.rectB - 1, 600, 500);
B.mark('edge-bottom');
await P(300);
await esc();                                          // end the tool
await P(300);

// "That saves repeating yourself, and it means the two sides stay identical
//  when you change a dimension later."
await B.at(at(O, 's01', 2) + 0.3);
await moveTo(MIRRORED[0], MIRRORED[1], 850);
B.mark('mirrored-half');

// Change the width: both halves follow, because the reflection is a feature.
await B.at(at(O, 's01', 2) + 3.1);
await moveTo(WIDTH_DIM[0], WIDTH_DIM[1], 800);
await P(150);
await page.mouse.down({ clickCount: 1 }); await P(60); await page.mouse.up({ clickCount: 1 });
await P(90);
await page.mouse.down({ clickCount: 2 }); await P(60); await page.mouse.up({ clickCount: 2 });
await P(800);
await page.keyboard.type('70', { delay: 150 });
await P(300);
await page.keyboard.press('Enter');
B.mark('width-changed');
await P(600);
await moveTo(MIRRORED[0] - 120, MID_Y + 40, 800);
B.mark('both-halves-updated');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => ({
  features: Array.from(document.querySelectorAll('.os-list-item-name'))
    .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 5),
  width: (() => { const m = (document.body.innerText || '').match(/Length:\s*([\d.]+)/); return m ? m[1] : null; })(),
}));
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
