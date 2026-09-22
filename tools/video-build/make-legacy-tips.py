#!/usr/bin/env python3
"""Reconstruct the legacy Onshape-tips narrations as video-build projects.

The legacy playlist is a full-desktop 1108x720 capture (menu bar, Dock, window
chrome). The new production is a clean tab-only 1920x1080 capture, so these
cannot be re-edited into the new look - they have to be re-shot. What is
reusable is the teaching content, recovered from each video's audio with
whisper and lightly corrected here.
"""
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'projects', 'onshape-tips')

# slug -> (title, card subtitle, narration)
VIDEOS = {
    'workspace-overview': (
        'Workspace Overview',
        'The dashboard, units, and moving around in 3D',
        "When you first log into Onshape, you're taken to a dashboard like this one. "
        "It shows your recently used files, and a bunch of other things down the left side. "
        "What we're interested in is the big Create button. "
        "Click that and you can create a new document: give it a name, hit Create, "
        "and now we're in our project workspace, where we can start sketching. "
        "Before we do anything, let's double check the units. "
        "You can do that from this menu here, and scroll down to Workspace units. "
        "Yours might be set to inches by default; if your team wants millimetres, "
        "switch to millimetres. Just make sure everybody on the team is using the same units. "
        "Click the green check mark. "
        "Now let's look at the workspace and how you navigate it. "
        "You can see three different planes: a front, a top, and a right plane, "
        "which represent our three-dimensional space. "
        "You can right-click and drag to spin around, and you'll see how you're moving "
        "a cube in three-dimensional space. You can see that here on the right side. "
        "You can also click on any one of these sides. "
        "If you want to see the back, click Back. "
        "If you want this corner, the back right corner, click that one. "
        "If you want the front, click this corner. Here I'm looking at the top front. "
        "And that's how you move around in a three-dimensional space."
    ),
    'basic-rectangle': (
        'A Basic Rectangle as My First Sketch',
        'Start a sketch on the Top plane and drive it with real numbers',
        "When we laser cut, we want to create a sketch in just two-dimensional space, "
        "so we don't really care about these different planes. We're going to work in one plane. "
        "I'm going to choose the Top plane, so it looks like you're looking down "
        "at the table where you're drawing. "
        "First I'll change my perspective to Top by clicking that, "
        "and now I'm just looking down at my work table. This is where I'm going to start drawing. "
        "To start drawing, I click the Sketch button here, and it asks me to select a sketch plane. "
        "As I said, I want to draw from the top, so click on that one, "
        "and now it's created a little sketch. We're in that top plane, "
        "where I can start adding the elements I want to laser cut. "
        "The first thing I'll do is create a very simple rectangle. "
        "When you click Sketch and click on the plane, you might have noticed that "
        "a bunch of different icons appeared up in the top menu bar. "
        "There are tools for drawing lines, for creating rectangles, circles, arcs, polygons, "
        "curves, points, and text. There are a few tools we'll cover, "
        "but for the very first thing to try, a rectangle is a good start. "
        "I'm going to click on that, and now I have my rectangle tool. "
        "I want to draw it on this line; you can see when I approach this line "
        "the dot turns orange. But you can draw anywhere within this plane. "
        "I'll just use this line as a starting point. Click, drag it out. "
        "You can see there are numbers that appear here at the bottom and on the left. "
        "Those are my dimensions. When I mouse over, you see it turns white, "
        "which means I can modify it. So I'm going to type in a different dimension of fifty, "
        "which means five centimetres, and hit Enter. "
        "Then it switches to the other edge of my rectangle, currently 33.313, "
        "and I'm going to turn it into 35. So enter 35, hit Enter. "
        "And there you go: we've drawn our first rectangle, with a 50 by 35 dimension."
    ),
    'updating-dimensions': (
        'Updating Dimensions',
        'Change a number and the sketch rebuilds',
        "Now, if I want to change the dimensions, I can double-click on any of these values. "
        "You might still be in the sketch tool, the way you are after starting the rectangle tool. "
        "You want to hit Escape first. "
        "And now you can select any of these dimensions, double-click them, and make changes. "
        "So from 35 to 30, for example. There you go. "
        "We've changed the dimension to a different value."
    ),
    'circle-to-cut-a-hole': (
        'Adding a Circle to a Rectangle to Cut a Hole',
        'A circle becomes a hole when the file reaches the cutter',
        "Next, I'm going to show you how to add a hole to cut in our rectangle. "
        "Say we want to cut a hole; the simplest way is with the circle tool. "
        "So I'll pick the circle tool, and then we can draw a circle anywhere we want to cut the hole. "
        "There we go, we have a circle. "
        "If we sent this to the laser cutter, it would cut out the square, "
        "and then it would cut a hole in the middle, and you'd have a square with a hole in it."
    ),
    'circle-in-the-center': (
        'Placing a Circle in the Center of a Rectangle',
        'Construction lines find an exact centre',
        "Typically you want to place holes at specific locations within your drawing. "
        "So I'm going to show you how to place the circle exactly in the middle of our square. "
        "First, let me get rid of this one. I'll select it and delete it. "
        "Now I have to find the exact center point of the square, "
        "and the way to do that is with a construction line. "
        "A construction line, which you can activate here, is a line that helps you draw, "
        "but it's not a line that will actually be cut by the laser cutter. "
        "Think of it as a light pencil stroke that supports your drawing, "
        "but it won't be in the final product when we send it to the laser cutter. "
        "So I'm going to draw a line right through the middle of the square. "
        "I start here, and you can see when I approach the centre of this line "
        "a little square highlights, which tells me this is the exact midpoint of that line. "
        "So I click there, and then I'm going to click right there. "
        "Now I've created a line smack in the middle of this rectangle. I hit Escape. "
        "And I'm going to do the same thing from here to there. "
        "So again, I click the line tool, make sure it's a construction line, "
        "find the midpoint, and drag down to the other midpoint. And there we go. "
        "Now we have two construction lines, one vertical and one horizontal, "
        "and the midpoint is where these two lines intersect. "
        "And now I can add my circle at that midpoint. So I click the circle tool, "
        "I select the middle, you see the square appear again, drag it out. "
        "And there we go: we have a circle right in the middle of our square. "
        "Say I want to make that a one centimetre diameter, type 10. "
        "And there we go. We've got a one centimetre hole in the middle of our square."
    ),
    'circle-on-a-corner': (
        'Adding a Circle at the Corner of a Square',
        'Anchor a hole to a corner',
        "Now let's look at placing a circle at a corner of the square. "
        "The same idea as centring it, but this time we anchor to a corner instead of a midpoint. "
        "I'll draw a construction line out from the corner, "
        "then place the circle where those lines meet, and dimension it from the edges. "
        "That gives us a hole at a known distance from the corner, "
        "rather than one that just looks about right."
    ),
    'mirroring-entities': (
        'Mirroring Entities to Avoid Repetitive Drawing',
        'Draw half, mirror the rest',
        "If a part is symmetrical, you only need to draw half of it. "
        "Draw one side, then use the mirror tool to reflect it across a centre line, "
        "and Onshape creates the other half for you. "
        "That saves repeating yourself, and it means the two sides stay identical "
        "when you change a dimension later."
    ),
    'trim-tool': (
        'Combining Shapes with the Trim Tool',
        'Cut away the lines you do not want',
        "Now let's combine shapes. Say we want a curved edge here on the right side. "
        "The first thing I'll do is use my three-point arc tool, "
        "and draw a line from here to there, and pull it out. Let's see, until here. "
        "So now I have a kind of rounded edge on the right side. "
        "But if you pay close attention, you'll see there's still a line going from here to there, "
        "which we don't want to keep, because otherwise we'd also send the laser cutter "
        "through here and it would cut off this rounded edge. "
        "So we're going to delete this line. "
        "I'll use the cut tool, or the trim tool as it's called, the scissors here. "
        "It's that one. And I'm going to remove this line and that line by clicking on them. "
        "So click. And now they're gone. "
        "So this is now a nice combined shape: our rectangle on the left, "
        "and the arc on the right side are one piece now."
    ),
    'laser-cut-joints': (
        'Creating Laser Cut Joints',
        'Finger joints that fit together',
        "Creating laser cut joints is a longer topic, so this one is a walkthrough of the whole idea. "
        "The goal is two pieces that slot together: fingers on one part, "
        "matching gaps on the other, sized to the thickness of your material. "
        "The important habit is the same one as everywhere else: "
        "measure the real material, then drive the drawing from that number "
        "rather than trusting a default."
    ),
}

FOOTER = 'Tufts University  \u00b7  Nolop Makerspace'


def main():
    for slug, (title, subtitle, narration) in VIDEOS.items():
        d = os.path.join(ROOT, slug)
        os.makedirs(d, exist_ok=True)
        json.dump({'s01': ' '.join(narration.split())},
                  open(os.path.join(d, 'script.json'), 'w'), indent=1)
        cfg = {
            'slug': slug,
            'workDir': f'~/Movies/ent164-onshape-tutorial/onshape-tips/{slug}',
            'output': f'~/Movies/ent164-onshape-tutorial/onshape-tips/{slug}.mp4',
            'eyebrow': 'ENT-164  \u00b7  ONSHAPE TIPS',
            'heading': title,
            'subtitle': subtitle,
            'footer': FOOTER,
            'titleDuration': 4.0,
            'endHeading': 'Happy making.',
            'endSubtitle': 'Measure the real part, draw it, export the DXF, and cut.',
            'endFooter': 'ENT-164  \u00b7  Intro to Making  \u00b7  Tufts University  \u00b7  Nolop Makerspace',
            'endCardDuration': 5.0,
            'voice': 'aura-2-thalia-en',
            'documentName': title,
            'lead': 0.0,
            'tail': 0.5,
            'takes': [{'name': 'take01', 'setup': 'setup-workspace', 'scenes': ['s01']}],
        }
        json.dump(cfg, open(os.path.join(d, 'video.json'), 'w'), indent=2)
        words = len(' '.join(narration.split()).split())
        print(f'  {slug:24s} {words:4d} words   {title}')

    print(f'\n{len(VIDEOS)} projects under {ROOT}')
    print('Each still needs: takes/take01.js + setup/setup-workspace.js, then record.')


if __name__ == '__main__':
    main()
