// TAKE 01 — Combining Shapes with the Trim Tool.
// The setup leaves the dimensioned rectangle's sketch open. We bulge the right
// side out with a 3-point arc, then trim away the straight edge it replaced.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

const TOP_R = [GEO.rectR, GEO.rectT];                    // top-right corner
const BOT_R = [GEO.rectR, GEO.rectB];                    // bottom-right corner
const MID_Y = Math.round((GEO.rectT + GEO.rectB) / 2);
const BULGE = [GEO.rectR + 96, MID_Y];                   // third point: pulled out
const ON_EDGE = [GEO.rectR, MID_Y];                      // the straight edge to remove

// "Now let's combine shapes."
await B.at(at(O, 's01', 0) + 0.1);
await moveTo(1330, 700, 650);
B.mark('shapes');

// "Say we want a curved edge here on the right side."
await B.at(at(O, 's01', 1) + 0.2);
await moveTo(GEO.rectR - 26, MID_Y - 30, 750);
B.mark('right-side');

// "The first thing I'll do is use my three-point arc tool, and draw a line
//  from here to there, and pull it out."
await B.at(at(O, 's01', 2) + 0.2);
const arcBtn = await toolBtn('3 point arc');
if (arcBtn) await moveTo(arcBtn.x + arcBtn.w / 2, arcBtn.y + arcBtn.h / 2, 700);
B.mark('hover-arc-tool');

await B.at(at(O, 's01', 2) + 1.6);
await clickToolBtn('3 point arc', { settle: 500 });
B.mark('picked-arc-tool');

await B.at(at(O, 's01', 2) + 3.1);
await clickAt(TOP_R[0], TOP_R[1], 450, 450);
B.mark('arc-from');

await B.at(at(O, 's01', 2) + 4.4);
await clickAt(BOT_R[0], BOT_R[1], 450, 450);
B.mark('arc-to');

// "Let's see, until here."
await B.at(at(O, 's01', 3) + 0.25);
await clickAt(BULGE[0], BULGE[1], 700, 620);
B.mark('arc-pulled-out');
await P(250);
await esc();                                             // end the arc tool
await P(300);

// "So now I have a kind of rounded edge on the right side."
await B.at(at(O, 's01', 4) + 0.3);
await moveTo(GEO.rectR + 40, MID_Y - 70, 750);
B.mark('rounded-edge');

// "But if you pay close attention, you'll see there's still a line going from
//  here to there, which we don't want to keep, because otherwise we'd also
//  send the laser cutter through here and it would cut off this rounded edge."
await B.at(at(O, 's01', 5) + 1.0);
await moveTo(ON_EDGE[0] - 8, ON_EDGE[1] - 56, 850);
B.mark('the-extra-line');
await B.at(at(O, 's01', 5) + 5.0);
await moveTo(ON_EDGE[0] - 8, ON_EDGE[1] + 60, 800);
B.mark('still-there');

// "So we're going to delete this line."
await B.at(at(O, 's01', 6) + 0.3);
await moveTo(ON_EDGE[0] - 6, ON_EDGE[1], 600);
B.mark('about-to-delete');

// "I'll use the cut tool, or the trim tool as it's called, the scissors here."
await B.at(at(O, 's01', 7) + 0.2);
const trimBtn = await toolBtn('Trim');
if (trimBtn) await moveTo(trimBtn.x + trimBtn.w / 2, trimBtn.y + trimBtn.h / 2, 800);
B.mark('hover-trim-tool');

// "It's that one."
await B.at(at(O, 's01', 8) + 0.1);
await clickToolBtn('Trim', { settle: 450 });
B.mark('picked-trim-tool');

// "And I'm going to remove this line and that line by clicking on them."
await B.at(at(O, 's01', 9) + 0.5);
await moveTo(ON_EDGE[0], ON_EDGE[1], 750);
B.mark('over-the-line');

// "So click."
await B.at(at(O, 's01', 10) + 0.15);
await clickAt(ON_EDGE[0], ON_EDGE[1], 550, 420);
B.mark('trimmed');

// "And now they're gone."
await B.at(at(O, 's01', 11) + 0.15);
await esc();                                             // end the trim tool
await moveTo(GEO.rectR + 120, MID_Y + 40, 700);
B.mark('gone');

// "So this is now a nice combined shape: our rectangle on the left, and the
//  arc on the right side are one piece now."
await B.at(at(O, 's01', 12) + 0.8);
await moveTo(GEO.rectL + 250, MID_Y - 20, 900);
B.mark('combined-shape');
await B.at(TOTAL - 0.15);

const state = await page.evaluate(() => ({
  features: Array.from(document.querySelectorAll('.os-list-item-name'))
    .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 5),
  fullyDefined: !Array.from(document.querySelectorAll('[data-bs-original-title]'))
    .some((e) => /not fully defined/i.test(e.getAttribute('data-bs-original-title') || '')),
}));
return { t0: B.t0, marks: B.marks, elapsed: B.elapsed(), state };
