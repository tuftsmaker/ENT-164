---
name: student-writing-style
description: Use when writing or editing any student-facing page for the Intro to Making Canvas site, including technical guides, content pages, and course framing.
---

# Student Writing Style

## Audience

You write pages for students in an intro to making course. The pages live in this repo and are published to Canvas. Most readers are new to the tools. Many read a guide while standing at a machine, hands busy, attention split. Write so a first-timer can follow each step without asking anyone.

Assume the reader is smart but has never used this tool. Define vocabulary. Do not talk down.

## Voice rules

- Short declarative sentences. One idea per sentence.
- Second person and imperative. "Clamp the board." Not "The board should be clamped."
- Be concrete. Name the exact button, menu path, setting, part, or value.
- Give an example before the general rule.
- Define a term the first time you use it, in one plain sentence.
- Say what the student should see after a step, so they know it worked.
- Say what commonly goes wrong and how to fix it.
- Friendly and calm. It is fine to admit something is tricky. Do not cheerlead.
- Paragraphs of three sentences or fewer.
- No em dashes. Use periods or commas.

## Page types

Decide the page type before writing. Do not mix them.

| Page type | Student's question | Model |
| --- | --- | --- |
| Technical guide | How do I do this task on this tool? | Adafruit Learning System guides |
| Content page | What is this, and why does it work this way? | Julia Evans |
| Course framing | Why are we making things this way? | Adam Savage, Every Tool's a Hammer |

Follow the models' structure and plainness. Do not imitate their catchphrases. If a technical guide needs a long explanation, link to a content page instead of stopping the steps.

## Technical guide template

1. Title: the task as a verb phrase. "Cut an acrylic box on the laser cutter."
2. What you'll make: one or two sentences and a photo of the result.
3. Before you start: required training, sign-offs, time needed.
4. Tools and materials: exact names, sizes, file types.
5. Steps: numbered, one action per step. Each step says what to do (exact control or setting), what the student should see, and includes a photo or screenshot when the step is visual.
6. If something goes wrong: symptom, likely cause, fix. The three to five most common problems.
7. Clean up: how to leave the machine and the space.
8. Next: one link to what to try next.

## Content page template

1. Open with the point: one or two sentences that answer the page's question.
2. A concrete example from this course.
3. The explanation: build from the example to the general idea. Name the confusing part, then clear it up.
4. Why it matters here: how it shows up in their projects.
5. Try it: one small check of understanding.

Keep content pages under about 600 words. Split longer ones.

## Safety

- Put **Safety:** in bold on its own line, right before the step it applies to.
- Name the hazard and the action. "Safety: Keep the lid closed while the laser runs. Open flames can start in seconds."
- Never soften a safety rule with "try to" or "it's a good idea to."
- Never invent a safety procedure, setting, or policy. If the course material does not state it, write [INSTRUCTOR: confirm] and flag it in your summary.

## Avoid

- Exclamation points and cheerleading ("Awesome!", "Let's dive in").
- "Simply", "just", "easy", "obviously".
- Passive voice in steps. Two actions in one step.
- Vague settings: "a bit", "fairly slow", "the right size".
- Long intros, recaps, "key takeaways".
- Guessed machine settings, dimensions, or policies.

## Example

Good step:

> 4. Focus the laser.
>
> Place the focus gauge on top of your material. Lower the laser head until the gauge just touches it. The gauge should slide out with light friction.
>
> If the gauge is loose, the cut will be wide and may not go through. Lower the head a little and check again.

Bad version of the same step:

> Next, you'll want to make sure the laser is properly focused! This is super important and easy to do. Simply adjust the head to the right height and you're good to go.

Good content page opening:

> Kerf is the width of material the tool removes when it cuts. A laser's kerf is about the width of a pencil line. A saw's kerf can be several millimeters.
>
> This matters when parts have to fit together. A slot drawn exactly 3 mm wide for 3 mm plywood comes out slightly wider, and the joint will be loose.

## Before you finish

- [ ] The page is one type: guide, content, or framing.
- [ ] The first sentence is useful on its own.
- [ ] Every step has one action and names the exact control or setting.
- [ ] Every visual step says what the student should see.
- [ ] Safety callouts sit right before their step.
- [ ] No "simply", "just", "easy", exclamation points, or em dashes.
- [ ] Every unknown setting or policy is marked [INSTRUCTOR: confirm].
- [ ] A student new to the tool could finish without help.
