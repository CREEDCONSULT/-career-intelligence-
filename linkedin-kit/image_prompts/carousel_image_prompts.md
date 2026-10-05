# Carousel Image Prompts

**How to use these:** image models render *backgrounds, textures, and abstract UI scenes* far better
than they render clean text. So each prompt describes the **visual world / background composition**;
overlay the actual slide copy in a design tool (Figma / Canva / Illustrator) using
`typography_and_layout.md`. A prompt for a "text-capable" tool is noted where relevant.

**Global spec (append to every prompt):**
> 1080×1350 vertical, dark data-dashboard aesthetic, deep navy near-black background #071018, faint
> technical square grid overlay in #29384C at low opacity, one soft blurred gold radial glow
> (#D5B56E, low opacity), thin gold divider lines, rounded dark UI cards with 1px #29384C borders,
> muted-slate and cream palette, warm gold accent, occasional soft blue (#7CB4FF) for data, premium
> executive product-strategy look, generous negative space, subtle film grain. No text unless
> specified. No people, no robots, no neon cyberpunk, no glitch, no circuit-board cliché, no stock
> photography, no cartoon mascots. Editorial, technical, calm, high-end.

---

## Carousel 1 — Proof-of-work
**Cover:** an abstract dark dashboard console at rest — a few floating rounded metric cards and a
faint "● live" pill, one large ghosted gold orb top-right, a thin gold divider, lots of empty space.
Feels like the title screen of a serious analytics instrument.
**Flow slide (5):** four connected rounded blocks left-to-right with thin gold arrows between them,
the third block washed soft blue, a small green checkmark on the last block. Abstract, label-less.
**Proof slide (7):** a 2×2 grid of empty rounded metric tiles ready for numbers, mono placeholder
lines, gold micro-labels, one tile subtly gold-bordered.

## Carousel 2 — System architecture
**Cover:** six faint horizontal layer-bands stacked behind an empty title zone, one band (third)
highlighted with a soft blue left-border, gold grid, ghosted orb behind. Architectural, quiet.
**Data slide (4):** five small source chips converging with thin lines into a single central card
(a "store"), on the dark grid. Abstract nodes, no readable text.
**Scorecard slide (8):** a horizontal strip of four rounded metric tiles with small green ticks,
gold under-labels, mono placeholder numbers.

## Carousel 3 — AI guardrails
**Cover:** a translucent gold shield motif ghosted behind an empty title zone, a thin blue accent
line, dark grid, one gold orb. Protective, not aggressive.
**Flow slides (4–8):** a vertical pipeline of rounded cards connected top-to-bottom with numbered
gold stage-markers (01–05); one card shows an abstract code block (blue), one shows an abstract
result-table, a thin gold line links a highlighted value in the answer card to a cell in the table;
a fork near the bottom with two small outcome chips (one muted-red, one blue).
**Text-capable tool variant (Slide 3 "The rule"):** same background, centered gold-bordered card
containing the exact line "The model does not get to invent numbers." in cream Inter, tight tracking.

## Carousel 4 — Productization
**Cover:** a slim horizontal 6-node roadmap timeline ghosted behind the title, node 1 filled gold,
the rest outlined and muted, connector line in #29384C, dark grid, gold orb.
**Wedge/moat slide (9):** two abstract shapes side by side — a gold wedge and a blue shield/moat
outline — on the grid, balanced, label-less.
**API slide (8):** a single central rounded "endpoint" card with three thin lines radiating out to
three small partner blocks. Clean integration diagram, abstract.

## Carousel 5 — Personal operating system
**Cover:** minimal — one ghosted gold orb, dark grid, a single thin gold divider, vast negative
space. The most restrained cover of the set (it's about method, not features).
**Method slide (8):** three equal rounded cards in a row with gold numeric markers 01/02/03, each
holding a small abstract motif (a broken-apart block, a small pipeline, a gear-less automation loop).
**Application slides (4–7):** a repeating single dashboard-tile frame (screenshot placeholder) with a
gold corner marker cycling 01→04, faint domain motifs behind (chart / layers / calendar).

---

## Reusable "hook cover" variant (for A/B testing frame 1)
A near-black slide, heavy grid, a single soft gold orb, one thin gold divider, and a lot of empty
space — engineered so bold cream text dropped on top reads instantly in the LinkedIn feed. Generate
several orb positions (top-right, center-right, lower-left) to test.

## Screenshot-frame template (for real dashboard captures)
Not an image-gen prompt — a compositing recipe: place the real screenshot inside a #0B1520 card with
a 1px #29384C border and 16px radius, dim the capture ~6%, set the grid behind it, add a mono caption
chip above (e.g. `MODULE · ASK THE DATA`). Use real frames of Ask, Career Advisor, Resume Studio, and
Market Brief wherever the message is "this is real."
