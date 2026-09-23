// TAKE 01 — A Basic Rectangle as My First Sketch.
// Unlike the other tips this one builds everything on camera: choose the plane,
// open the sketch, meet the toolbar, draw the rectangle and type both
// dimensions. The setup only leaves a clean Part Studio.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

// "When we laser cut, we want to create a sketch in just two-dimensional space,
//  so we don't really care about the third dimension."
await B.at(at(O, 's01', 0) + 0.5);
await moveTo(1250, 640, 900);
B.mark('workspace');

// "We're going to work in one plane."
await B.at(at(O, 's01', 1) + 0.3);
await moveTo(1150, 520, 700);
B.mark('one-plane');

// "I'm going to choose the Top plane, so it looks like you're looking down at
//  the table where you're drawing."
await B.at(at(O, 's01', 2) + 0.4);
const topRow = await boxOf('Top', { exact: true, maxX: 300, minY: 150 });
if (topRow) await clickAt(topRow.x + topRow.w / 2, topRow.y + topRow.h / 2, 700, 600);
B.mark('top-chosen');

// "First I'll change my perspective to Top by clicking that, and now I'm just
//  looking down at my work table."
await B.at(at(O, 's01', 3) + 0.5);
await moveTo(1770, 160, 800);
await page.keyboard.press('n'); await P(900);
await page.keyboard.press('f'); await P(1200);
B.mark('view-top');

// "This is where I'm going to start drawing."
await B.at(at(O, 's01', 4) + 0.3);
await moveTo(1200, 700, 800);
B.mark('where-to-draw');

// "To start drawing, I click the Sketch button here, and it asks me to select a
//  sketch plane."
await B.at(at(O, 's01', 5) + 0.2);
const sketchBtn = await toolBtn('Create new sketch');
if (sketchBtn) await moveTo(sketchBtn.x + sketchBtn.w / 2, sketchBtn.y + sketchBtn.h / 2, 750);
B.mark('sketch-button');
await B.at(at(O, 's01', 5) + 2.4);
await clickToolBtn('Create new sketch', { settle: 700 });
B.mark('sketch-open');

// "As I said, I want to draw from the top, so click on that one, and now it's
//  created a little sketch."
await B.at(at(O, 's01', 6) + 0.3);
const topDatum = await boxOf('Top', { exact: true, maxX: 300, minY: 150 });
if (topDatum) await clickAt(topDatum.x + topDatum.w / 2, topDatum.y + topDatum.h / 2, 900, 550);
B.mark('plane-picked');

// "We're in that top plane, where I can start adding the elements I want to
//  laser cut."
await B.at(at(O, 's01', 7) + 0.4);
await page.keyboard.press('n'); await P(900);           // same ending as the shared helper
await page.keyboard.press('f'); await P(1400);
await esc(); await P(300);
B.mark('in-the-plane');

// "The first thing I'll do is create a very simple rectangle."
await B.at(at(O, 's01', 8) + 0.4);
await moveTo(1330, 720, 800);
B.mark('simple-rectangle');

// "When you click Sketch and click on the plane, you might have noticed that a
//  bunch of different icons appear..."
await B.at(at(O, 's01', 9) + 0.6);
await moveTo(320, 58, 900);
B.mark('toolbar-start');

// "There are tools for drawing lines, for creating rectangles, circles, arcs,
//  polygons, curves, points..."
await B.at(at(O, 's01', 10) + 0.3);
await moveTo(560, 58, 900);
await moveTo(760, 58, 900);
B.mark('toolbar-sweep');
await B.at(at(O, 's01', 10) + 4.6);
await moveTo(960, 58, 800);
B.mark('toolbar-more');

// "There are a few tools we'll cover, but for the very first thing to try, a
//  rectangle is a good start."
await B.at(at(O, 's01', 11) + 0.4);
const rectBtn = await toolBtn('Corner rectangle');
if (rectBtn) await moveTo(rectBtn.x + rectBtn.w / 2, rectBtn.y + rectBtn.h / 2, 800);
B.mark('rectangle-tool-hover');

// "I'm going to click on that, and now I have my rectangle tool."
await B.at(at(O, 's01', 12) + 0.3);
await clickToolBtn('Corner rectangle', { settle: 550 });
B.mark('rectangle-tool');

// "I want to draw it on this line; you can see when I approach this line the
//  dot turns orange."
await B.at(at(O, 's01', 13) + 0.6);
await moveTo(GEO.origin[0] - 90, GEO.origin[1] + 30, 800);
await moveTo(GEO.origin[0] + 4, GEO.origin[1] + 3, 800);      // snap onto the line
B.mark('snapped-to-line');

// "But you can draw anywhere within this plane."
await B.at(at(O, 's01', 14) + 0.3);
await moveTo(GEO.origin[0] + 320, GEO.origin[1] + 260, 800);
B.mark('anywhere');

// "I'll just use this line as a starting point."
await B.at(at(O, 's01', 15) + 0.4);
await moveTo(GEO.origin[0] + 4, GEO.origin[1] + 3, 750);
B.mark('start-on-line');

// "Click, drag it out."
await B.at(at(O, 's01', 16) + 0.15);
await page.mouse.move(GEO.origin[0], GEO.origin[1], { steps: 4 });
await P(120);
await page.mouse.down();
await P(140);
await moveTo(GEO.corner2[0], GEO.corner2[1], 900);            // drag the rectangle out
await P(200);
await page.mouse.up();
await P(400);
B.mark('dragged-out');

// "You can see there are numbers that appear here at the bottom and on the left.
//  Those are my dimensions."
await B.at(at(O, 's01', 17) + 0.4);
await moveTo(GEO.corner2[0] - 60, GEO.corner2[1] - 40, 800);
B.mark('numbers-appear');

// "When I mouse over, you see it turns white, which means I can modify it."
await B.at(at(O, 's01', 19) + 0.5);
await moveTo(GEO.origin[0] + 250, GEO.origin[1] + 48, 800);   // onto the width dimension
B.mark('over-dimension');

// "So I'm going to type in a different dimension of fifty, which means five
//  centimetres, and hit Enter."
await B.at(at(O, 's01', 20) + 0.5);
await page.keyboard.type('50', { delay: 130 });
await P(320);
await page.keyboard.press('Enter');
B.mark('typed-50');
await P(600);

// "Then it switches to the other edge of my rectangle, currently 33.313, and
//  I'm going to turn it into 35."
await B.at(at(O, 's01', 21) + 0.6);
await moveTo(GEO.corner2[0] + 44, GEO.corner2[1] - 120, 800);  // the height dimension
B.mark('other-edge');

// "So enter 35, hit Enter."
await B.at(at(O, 's01', 22) + 0.4);
await page.keyboard.type('35', { delay: 130 });
await P(320);
await page.keyboard.press('Enter');
B.mark('typed-35');
await P(700);

// "And there you go: we've drawn our first rectangle, with a 50 by 35
//  dimension."
await B.at(at(O, 's01', 23) + 0.5);
await page.keyboard.press('f'); await P(1300);
await esc(); await P(300);
await moveTo(GEO.origin[0] + 330, GEO.origin[1] + 250, 900);
B.mark('first-rectangle');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => {
  const t = document.body.innerText || '';
  return {
    dims: (t.match(/[\d.]+\s*mm/g) || []).slice(0, 6),
    features: Array.from(document.querySelectorAll('.os-list-item-name'))
      .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 6),
  };
});
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
