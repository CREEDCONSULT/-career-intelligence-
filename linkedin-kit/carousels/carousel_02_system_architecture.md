# Carousel 2 — "How I designed the Career Intelligence Dashboard"

**Purpose:** explain product architecture.
**Slides:** 10 · **Size:** 1080×1350 · **System:** dark dashboard.

---

### Slide 1 — Cover
`ARCHITECTURE · 02`
**How I designed the**
**Career Intelligence Dashboard.**
Six layers. One rule. A system you can actually trust.
*Design: grid overlay, faint six-block column ghosted behind the title.*

### Slide 2 — Start with the user problem
`START HERE`
**Not "what can the model do."**
**"What decision is the user stuck on?"**
People need clearer career decisions grounded in reality — not another opinion.
*Design: a single user-journey node highlighted gold at the left of a faint path.*

### Slide 3 — Break the system into layers
`THE SHAPE`
**Good AI products are layers, not prompts.**
Data · Analytics · AI · UX · Evaluation · Productization.
The model lives in exactly one of them.
*Design: six stacked cards, numbered 01–06, each with an eyebrow label. Gold left-border on card 03 (AI).*

### Slide 4 — Data layer
`LAYER 01 · DATA`
**Where credibility is earned.**
Job Bank · Statistics Canada · Indeed Hiring Lab · Lightcast · NOC 2021.
Five sources → one clean, queryable store.
*Design: five source chips flowing into a single "DuckDB" card. Thin borders, cream labels.*

### Slide 5 — Analytics layer
`LAYER 02 · ANALYTICS`
**Signals become intelligence.**
Raw postings → skills in demand, salary ranges, role demand, hiring trends.
*Design: a "raw signal" bar transforming into three metric tiles (Skills / Salary / Demand).*

### Slide 6 — AI layer
`LAYER 03 · AI`
**Explains. Summarizes. Guides.**
**Never invents.**
The model writes the query. The database returns the numbers.
*Design: blue-accented card with a small "no-invent" guardrail badge (shield + ✓).*

### Slide 7 — UX layer
`LAYER 04 · UX`
**8 modules make it usable.**
Ask the Data · Career Advisor · Skill Demand · Salary Ranges · Role Fit · Resume Studio · Market Context · Market Brief.
*Design: 4×2 grid of small module tiles with icons. Even spacing, rounded corners.*

### Slide 8 — Evaluation layer
`LAYER 05 · EVALUATION`
**Trust has to be measured.**
80% query accuracy · 0 invented numbers · 0.94 brief faithfulness · 5/5 refusals.
*Design: a horizontal "scorecard" with four metrics, green ticks, gold labels.*

### Slide 9 — Product layer
`LAYER 06 · PRODUCT`
**This can scale into a product.**
Open demo → gated beta → personal layer → coach/institution → new markets → API.
*Design: a slim 6-node roadmap timeline, node 1 filled gold ("you are here").*

### Slide 10 — CTA
`THE TAKEAWAY`
**Good AI products are designed as systems, not prompts.**
The architecture *is* the product.
Full teardown + live app in the comments.
*Design: bold closing line, gold underline, monogram sign-off.*

---
**Image prompt:** `/image_prompts/carousel_image_prompts.md` → Carousel 2. Diagram prompts in `architecture_diagram_prompts.md`.
