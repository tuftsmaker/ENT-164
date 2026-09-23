// TAKE 01 — Workspace Overview.
// A tour of the workspace: the feature list, the toolbar, the three planes, and
// how to move around in 3D. Nothing is drawn, so every beat is a cursor move or
// a view-cube click - and the clicks are the only thing that changes the screen.
const SIDS = ['s01'];
const O = offs(SIDS);
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take01');
await scenePrep();

// The view cube sits in the top-right corner; these are its Back face, an upper
// corner, and the front.
const CUBE_BACK = [1822, 158];
const CUBE_CORNER = [1862, 120];
const CUBE_FRONT = [1791, 194];

// "Where you'll spend all of your time in Onshape is here, in the workspace."
await B.at(at(O, 's01', 0) + 0.4);
await moveTo(1000, 620, 900);
B.mark('workspace');

// "Down the left is the feature list: every sketch, every part, everything you
//  make, in order."
await B.at(at(O, 's01', 1) + 0.5);
await moveTo(150, 300, 900);
await moveTo(170, 470, 700);
B.mark('feature-list');

// "Across the top is the toolbar, and it changes to match what you're doing."
await B.at(at(O, 's01', 2) + 0.4);
await moveTo(420, 58, 850);
await moveTo(760, 58, 800);
B.mark('toolbar');

// "Out in the middle is the space itself."
await B.at(at(O, 's01', 3) + 0.2);
await moveTo(1000, 640, 800);
B.mark('the-space');

// "You can see three planes: a front, a top, and a right, which stand in for
//  our three dimensions."
await B.at(at(O, 's01', 4) + 0.6);
await moveTo(940, 300, 800);       // the front plane, upper left
B.mark('front-plane');
await B.at(at(O, 's01', 4) + 3.4);
await moveTo(1120, 560, 800);      // the top plane, crossing the middle
B.mark('top-plane');
await B.at(at(O, 's01', 4) + 5.6);
await moveTo(1000, 700, 800);      // the right plane
B.mark('right-plane');

// "Right-click and drag to spin the view around, and you're turning this cube
//  in the top right corner."
await B.at(at(O, 's01', 5) + 0.5);
await orbit(1000, 640, 1180, 560, 1800);
B.mark('orbited');
await P(300);
await moveTo(1830, 160, 800);
B.mark('the-cube');

// "You can also click the cube's faces to jump straight to a view."
await B.at(at(O, 's01', 6) + 0.3);
await clickAt(CUBE_BACK[0], CUBE_BACK[1], 800, 600);
B.mark('view-back');

// "Back looks from behind, a corner gives you an angle, and this one is the
//  front."
await B.at(at(O, 's01', 7) + 0.4);
await clickAt(CUBE_CORNER[0], CUBE_CORNER[1], 800, 600);
B.mark('view-corner');
await B.at(at(O, 's01', 7) + 2.6);
await clickAt(CUBE_FRONT[0], CUBE_FRONT[1], 850, 600);
B.mark('view-front');

// "And that's how you find your way around a three-dimensional space."
await B.at(at(O, 's01', 8) + 0.3);
await moveTo(1200, 640, 900);
B.mark('done');
await B.at(TOTAL - 0.15);

return { t0: B.t0, marks: B.marks, elapsed: B.elapsed() };
