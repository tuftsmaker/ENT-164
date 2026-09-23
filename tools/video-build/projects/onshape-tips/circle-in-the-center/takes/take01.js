// TAKE 01 — Placing a Circle in the Center of a Rectangle.
// The setup leaves a dimensioned rectangle plus one stray circle. The take
// deletes the circle, crosses the rectangle with two construction lines, then
// puts the circle on their intersection and types its diameter.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const MID_X = Math.round((GEO.rectL + GEO.rectR) / 2);   // 1391
const MID_Y = Math.round((GEO.rectT + GEO.rectB) / 2);   // 747
const LEFT_MID = [GEO.rectL, MID_Y];
const RIGHT_MID = [GEO.rectR, MID_Y];
const TOP_MID = [MID_X, GEO.rectT];
const BOT_MID = [MID_X, GEO.rectB];
const CENTRE = [MID_X, MID_Y];
const CIRC_R = [MID_X + 31, MID_Y];                       // 10mm diameter at 6.18 px/mm

// "Typically you want to place holes at specific locations within your drawing."
await B.at(at(O, 's01', 0) + 0.4);
await moveTo(1500, 700, 850);
B.mark('thinking-about-holes');

// "So I'm going to show you how to place the circle exactly in the middle of
//  our square."
await B.at(at(O, 's01', 1) + 0.5);
await moveTo(GEO.circleC[0], GEO.circleC[1], 800);
B.mark('the-stray-circle');

// "First, let me get rid of this one. I'll select it and delete it."
await B.at(at(O, 's01', 2) + 0.4);
await clickAt(GEO.circleC[0], GEO.circleC[1], 600, 550);
B.mark('circle-selected');
await B.at(at(O, 's01', 3) + 0.2);
await page.keyboard.press('Delete');
await P(700);
await moveTo(GEO.circleC[0] + 90, GEO.circleC[1] + 60, 700);
B.mark('circle-deleted');

// "Now I have to find the exact center point of the square, and the way to do
//  that is with a construction line."
await B.at(at(O, 's01', 4) + 0.5);
const conBtn = await toolBtn('Construction');
if (conBtn) await moveTo(conBtn.x + conBtn.w / 2, conBtn.y + conBtn.h / 2, 850);
B.mark('construction-hover');

// "A construction line, which you can activate here, is a line that helps you
//  draw, but it's not a line..."
await B.at(at(O, 's01', 5) + 0.3);
await clickToolBtn('Construction', { settle: 450 });
B.mark('construction-on');

// "Think of it as a light pencil stroke that supports your drawing, but it
//  won't be in the final product."
await B.at(at(O, 's01', 6) + 0.5);
await moveTo(MID_X - 120, MID_Y - 60, 800);
B.mark('pencil-stroke');

// "So I'm going to draw a line right through the middle of the square."
await B.at(at(O, 's01', 7) + 0.3);
await clickToolBtn('Line', { settle: 450 });
B.mark('line-tool');

// "I start here, and you can see when I approach the centre of this line a
//  little square highlights..."
await B.at(at(O, 's01', 8) + 0.5);
await moveTo(LEFT_MID[0] + 6, LEFT_MID[1] + 2, 800);
B.mark('midpoint-highlight');

// "So I click there, and then I'm going to click right there."
await B.at(at(O, 's01', 9) + 0.15);
await clickAt(LEFT_MID[0], LEFT_MID[1], 450, 450);
B.mark('horizontal-from');
await clickAt(RIGHT_MID[0], RIGHT_MID[1], 550, 550);
B.mark('horizontal-to');

// "Now I've created a line smack in the middle of this rectangle."
await B.at(at(O, 's01', 10) + 0.4);
await moveTo(MID_X - 200, MID_Y - 34, 700);
B.mark('horizontal-there');

// "I hit Escape."
await B.at(at(O, 's01', 11) + 0.1);
await esc(); await P(250);
B.mark('escaped');

// "And I'm going to do the same thing from here to there."
await B.at(at(O, 's01', 12) + 0.3);
await clickToolBtn('Line', { settle: 400 });
B.mark('line-tool-again');

// "So again, I click the line tool, make sure it's a construction line, find
//  the midpoint, and drag down..."
await B.at(at(O, 's01', 13) + 0.5);
await moveTo(TOP_MID[0] + 2, TOP_MID[1] + 6, 750);
B.mark('top-midpoint');
await B.at(at(O, 's01', 13) + 2.6);
await clickAt(TOP_MID[0], TOP_MID[1], 450, 450);
B.mark('vertical-from');
await clickAt(BOT_MID[0], BOT_MID[1], 550, 550);
B.mark('vertical-to');

// "And there we go."
await B.at(at(O, 's01', 14) + 0.2);
await esc(); await P(250);
B.mark('both-drawn');

// "Now we have two construction lines, one vertical and one horizontal, and
//  the midpoint is where these..."
await B.at(at(O, 's01', 15) + 0.8);
await moveTo(CENTRE[0] + 14, CENTRE[1] - 14, 800);
B.mark('the-intersection');

// "And now I can add my circle at that midpoint."
await B.at(at(O, 's01', 16) + 0.5);
await clickToolBtn('Center point circle', { settle: 450 });
B.mark('circle-tool');

// "So I click the circle tool, I select the middle, you see the square appear
//  again, drag it out."
await B.at(at(O, 's01', 17) + 0.2);
await clickAt(CENTRE[0], CENTRE[1], 500, 500);
B.mark('circle-centre');
await clickAt(CIRC_R[0], CIRC_R[1], 800, 500);
B.mark('circle-pulled-out');

// "And there we go: we have a circle right in the middle of our square."
await B.at(at(O, 's01', 18) + 0.3);
await moveTo(CENTRE[0] + 80, CENTRE[1] + 70, 700);
B.mark('circle-in-the-middle');

// "Say I want to make that a one centimetre diameter, type 10."
await B.at(at(O, 's01', 19) + 0.4);
await page.keyboard.type('10', { delay: 130 });
await P(320);
await page.keyboard.press('Enter');
B.mark('typed-10');
await P(600);

// "And there we go. We've got a one centimetre hole in the middle of our
//  square."
await B.at(at(O, 's01', 20) + 0.1);
await esc(); await P(300);
await moveTo(CENTRE[0] + 130, CENTRE[1] + 110, 800);
B.mark('the-hole');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => {
  const t = document.body.innerText || '';
  return { dims: (t.match(/[\d.]+\s*mm/g) || []).slice(0, 5) };
});
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
