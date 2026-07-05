# Career Intelligence Dashboard — LinkedIn Content Kit

**Campaign:** AI as Infrastructure — Building My Career Intelligence System
**For:** Mesomachukwu Mezie-Akabudu · AI Product & Strategy Lead · Toronto
**Positioning:** I don't only *use* AI. I *build systems* with AI.

## Assets
- **Live app:** https://career-intelligence-production.up.railway.app/
- **Repo:** https://github.com/CREEDCONSULT/-career-intelligence-
- **LinkedIn:** https://www.linkedin.com/in/mesomachukwu-mezie-akabudu-a2606b236/

## What's real (use these numbers — they're verified, not marketing)
| Fact | Value |
|------|-------|
| Toronto job postings analyzed | 97,227 (12 months) |
| Distinct skills mapped | 5,148 |
| Occupations covered | 471 |
| Data sources | Job Bank, Statistics Canada, Indeed Hiring Lab, Lightcast, NOC 2021 |
| Text-to-SQL execution accuracy | 80% on a held-out gold set |
| Wrong numbers ever shown to a user | 0 (guaranteed by design) |
| Monthly brief faithfulness | 0.94 |
| Out-of-scope questions refused | 5/5 |
| Resume→role match top-5 accuracy | 8/8 test profiles |
| Product modules shipped | 8 |
| Automated tests | 100, green in CI |

## The one-line thesis
> Career advice shouldn't just *sound* intelligent. It should be *grounded*. The model is not the source of truth — the system is.

## Folder map
```
/strategy      campaign strategy, audience positioning, narrative pillars, roadmap
/captions      12-post caption bank + 4-week calendar
/carousels     5 carousels, written slide-by-slide
/design_system brand guide, palette, type, motifs, slide rules
/html          5 reusable dark-dashboard pages (landing, case study, carousel, roadmap, architecture)
/image_prompts generation prompts for every carousel + diagrams + roadmap
/profile       featured section, about insert, experience bullets
```

## How to run the campaign (fast path)
1. Publish the **Featured Section** + **About insert** (see `/profile`) — set the frame first.
2. Post **Week 1** captions + **Carousel 5 (How I use AI to stay ahead)** or **Carousel 1** as the opener.
3. Follow the **4-week calendar** in `/captions/post_sequence_calendar.md`.
4. Generate slide art with `/image_prompts` (dark dashboard system, no robots, no neon).
5. Host the **campaign landing page** (`/html/campaign_landing_page.html`) and link it from the Featured Section.
