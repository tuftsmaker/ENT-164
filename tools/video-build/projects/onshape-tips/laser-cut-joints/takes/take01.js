// TAKE 01 — Creating Laser Cut Joints.
// The setup leaves a finger-and-slot joint drawn, with the slot dimensioned at
// the material thickness. The take shows the two parts, then changes that one
// number - which is the whole point of the tip.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const MM = GEO.scale;
const PX = 1100, PY = 660;
const NX0 = PX + 114, NX1 = NX0 + Math.round(3 * MM), NY = PY + Math.round(10 * MM);
const FINGER = [Math.round((NX0 + NX1) / 2), NY - 60];
const SLOT = [Math.round((NX0 + NX1) / 2), NY];
const DIM = [Math.round((NX0 + NX1) / 2), NY + 46];

// "Some joints you don't glue at all."
await B.at(at(O, 's01', 0) + 0.2);
await moveTo(1250, 700, 800);
B.mark('the-joint');

// "You cut fingers on one piece and matching slots on the other, and they press
//  together."
await B.at(at(O, 's01', 1) + 0.4);
await moveTo(FINGER[0], FINGER[1], 750);
B.mark('the-finger');
await B.at(at(O, 's01', 1) + 2.8);
await moveTo(SLOT[0], SLOT[1] + 4, 750);
B.mark('the-slot');

// "Everything about that joint comes down to one number: the thickness of your
//  material."
await B.at(at(O, 's01', 2) + 0.4);
await moveTo(DIM[0] + 26, DIM[1], 800);
B.mark('the-number');

// "Measure it with calipers rather than trusting the label."
await B.at(at(O, 's01', 3) + 0.3);
await moveTo(FINGER[0] + 74, FINGER[1] + 30, 800);
B.mark('measure');

// "Plywood sold as three millimetres often measures a little under, and the
//  laser takes a little more as it cuts."
await B.at(at(O, 's01', 4) + 0.6);
await moveTo(DIM[0] - 8, DIM[1] + 6, 800);
B.mark('the-label');

// "So draw your slots at the thickness you measured, and cut a small test piece
//  first."
await B.at(at(O, 's01', 5) + 0.5);
await moveTo(DIM[0], DIM[1], 700);
await P(150);
await page.mouse.down({ clickCount: 1 }); await P(60); await page.mouse.up({ clickCount: 1 });
await P(90);
await page.mouse.down({ clickCount: 2 }); await P(60); await page.mouse.up({ clickCount: 2 });
await P(800);
B.mark('dimension-open');

// "If the fit is loose, take a tenth of a millimetre off the slot and cut the
//  test again."
await B.at(at(O, 's01', 6) + 0.6);
await page.keyboard.type('2.9', { delay: 130 });
await P(320);
await page.keyboard.press('Enter');
B.mark('typed-2-9');
await P(700);

// "Once the test fits, everything you cut from that sheet will fit too."
await B.at(at(O, 's01', 7) + 0.4);
await moveTo(SLOT[0] + 40, SLOT[1] + 20, 800);
B.mark('the-fit');
await B.at(at(O, 's01', 7) + 2.8);
await moveTo(FINGER[0] + 40, FINGER[1] + 10, 800);
B.mark('both-parts');

// "And because the joint is dimensioned from that one number, changing it
//  changes the joint."
await B.at(at(O, 's01', 8) + 0.5);
await moveTo(DIM[0], DIM[1] - 4, 850);
B.mark('dimension-changed');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => {
  const t = document.body.innerText || '';
  return { dims: (t.match(/[\d.]+\s*mm/g) || []).slice(0, 5) };
});
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
