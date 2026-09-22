// TAKE 01 — Updating Dimensions.
// Escape out of the sketch tool, double-click a dimension, change it.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const WIDTH_DIM = [1390, 602];   // the "100" dimension line (measured)

// "Once a sketch is dimensioned, you can change any number and the shape rebuilds."
await B.at(at(O, 's01', 0) + 0.4);
B.mark('showing-sketch');

// "...you might still be in the sketch tool, so hit Escape first."
await B.at(at(O, 's01', 1) + 0.6);
await page.keyboard.press('Escape');
B.mark('escaped');
await P(500);

// "Now double-click any dimension."
await B.at(at(O, 's01', 2) + 0.3);
await moveTo(WIDTH_DIM[0], WIDTH_DIM[1], 900);
B.mark('hover-dim');
await B.at(at(O, 's01', 2) + 1.2);
await page.mouse.move(WIDTH_DIM[0], WIDTH_DIM[1], { steps: 3 });
await P(160);
await page.mouse.down({ clickCount: 1 }); await P(60); await page.mouse.up({ clickCount: 1 });
await P(90);
await page.mouse.down({ clickCount: 2 }); await P(60); await page.mouse.up({ clickCount: 2 });
await P(900);
B.mark('double-clicked');

// "Let's take this one from one hundred down to eighty."
await B.at(at(O, 's01', 3) + 0.5);
await page.keyboard.type('80', { delay: 150 });
B.mark('typed-80');

// "Type the new value and press Enter."
await B.at(at(O, 's01', 4) + 0.4);
await page.keyboard.press('Enter');
B.mark('committed');
await P(600);

// "And the rectangle rebuilds to match."
await B.at(at(O, 's01', 5) + 0.4);
await moveTo(1150, 760, 900);
B.mark('rebuilt');
await B.at(TOTAL - 0.15);

const width = await page.evaluate(() => {
  const t = document.body.innerText;
  const m = t.match(/Length:\s*([\d.]+)\s*mm/);
  return m ? m[1] : null;
});
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), measuredWidth: width };
