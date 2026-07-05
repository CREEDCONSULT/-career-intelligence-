# Carousel 3 — "The AI guardrail pattern behind the dashboard"

**Purpose:** show mastery of AI trust, hallucination, and evaluation.
**Slides:** 10 · **Size:** 1080×1350 · **System:** dark dashboard.

---

### Slide 1 — Cover
`GUARDRAILS · 03`
**The AI guardrail pattern**
**behind the dashboard.**
How the model gets to be useful — and never gets to lie.
*Design: grid overlay, a shield motif ghosted behind title in gold. Blue accent line.*

### Slide 2 — The risk
`THE RISK`
**AI can sound confident and still be wrong.**
The danger isn't error. It's *confident* error — a fluent answer with a made-up number inside.
*Design: a mock answer card with a subtly highlighted number, muted-red warning chip "unverified".*

### Slide 3 — The design rule
`THE RULE`
**The model does not get to invent numbers.**
One hard constraint that changes everything downstream.
*Design: single bold rule on a gold-bordered card. Everything else empty.*

### Slide 4 — Step 1
`FLOW · 01`
**You ask a question.**
"Which occupations pay the most in Toronto?"
*Design: chat-input tile at the top of a vertical flow with numbered stage markers.*

### Slide 5 — Step 2
`FLOW · 02`
**The system turns it into a structured query.**
Plain English → validated SQL. Not a guess — a query.
*Design: arrow down to a "SQL" code card; a small "validated" green tick badge.*

### Slide 6 — Step 3
`FLOW · 03`
**The query is validated, then run against the data.**
Read-only. Checked for safety and shape *before* it ever touches the database.
*Design: guardrail checkpoint block — shield icon, "SELECT-only · read-only · row-capped".*

### Slide 7 — Step 4
`FLOW · 04`
**The AI explains only what the data returned.**
Every number in the answer must exist in the result set. If it doesn't, it's stripped.
*Design: result table tile → answer card, with a gold link line showing "number matched".*

### Slide 8 — Step 5
`FLOW · 05`
**If the answer isn't supported, the system refuses or clarifies.**
Out-of-scope? It declines. Unverified figure? It shows the table, not a sentence.
*Design: two outcome chips — "REFUSE" (muted red) and "SHOW DATA" (blue) — with a fork arrow.*

### Slide 9 — The distinction
`WHY IT MATTERS`
**A chatbot improvises. A product refuses.**
That's the line between something that demos well and something you can trust.
Measured: 80% accuracy · 0 invented numbers shown · 5/5 out-of-scope refusals.
*Design: two-column contrast — "Chatbot: improvises" vs "Product: refuses" — scorecard strip below.*

### Slide 10 — CTA
`THE TAKEAWAY`
**More AI tools need less magic and more verification.**
The trust isn't in the model. It's in the checks around it.
Repo's public — the guardrails are in the code. Link in comments.
*Design: closing statement, gold underline, monogram sign-off.*

---
**Image prompt:** `/image_prompts/carousel_image_prompts.md` → Carousel 3.
