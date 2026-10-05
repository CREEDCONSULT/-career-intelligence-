# Typography & Layout

## Typefaces
- **Primary (titles + UI):** Inter, or Söhne / Geist / Neue Haas Grotesk if available. Clean, modern, geometric-humanist sans. Tight tracking on big titles.
- **Mono (metrics, code, labels):** Geist Mono, JetBrains Mono, or IBM Plex Mono. Use for numbers, SQL, chips, stage markers.
- Fallback stack: `Inter, "Söhne", system-ui, -apple-system, Segoe UI, Roboto, sans-serif`.

## Type scale (1080×1350 slide)
| Element | Size (px) | Weight | Color | Notes |
|---------|-----------|--------|-------|-------|
| Eyebrow label | 22–26 | 600, mono, +8% tracking, UPPERCASE | gold `#D5B56E` | e.g. `ARCHITECTURE · 02` |
| Slide title | 78–104 | 700, tracking −2% | cream `#F7F1E8` | 2–4 words per line max |
| Subhead | 40–52 | 600 | cream | supports the title |
| Body | 30–36 | 400–500 | slate `#AEB9C8` | short lines, generous leading (1.4) |
| Metric number | 64–96 | 700, mono | cream | gold or blue if it's the hero number |
| Metric label | 20–24 | 600, mono, UPPERCASE | gold/slate | under the number |
| Chip / pill | 20–24 | 600, mono | context color | pill background at 12–14% opacity |
| Footer / sign-off | 22–26 | 500 | slate | monogram + name |

## Layout grid
- **Canvas:** 1080×1350. **Safe margins:** 88px all sides (LinkedIn crops edges on some views).
- **Baseline column:** single 904px content column; use a faint 12-col grid only as background texture.
- **Vertical rhythm:** eyebrow → title → divider (gold, 2px, ~120px wide) → content → footer.
- **Spacing unit:** 8px base. Gaps in multiples (16 / 24 / 32 / 48 / 64).
- **One idea per slide.** If it needs two columns of text, it's two slides.

## Composition principles
1. **Top-left anchored** eyebrow + title. Content flows down. Footer pinned bottom-left.
2. **Whitespace is a feature** — this is an executive system, not a poster. Leave 30–40% breathing room.
3. **Left-align almost everything.** Center only single hero statements (Slide 8 / closers).
4. **Numbers are heroes.** When a slide has a metric, it should be the largest non-title element.
5. **Consistent header zone** across a carousel so slides feel like one system when swiped.

## Card anatomy (the reusable unit)
- Background `#0B1520`, 1px border `#29384C`, radius **16px**, padding 28–32px.
- Optional 1px top inner-sheen `rgba(255,255,255,0.03)`.
- Optional 3px left border in accent color to denote type (gold = key, blue = AI, green = verified).
- Card label: mono eyebrow top-left; value/body below.

## Do / Don't
- **Do** keep titles to 2–4 words per line. **Don't** justify text.
- **Do** use mono for every number and label. **Don't** mix more than 2 type families.
- **Do** let one gold element lead. **Don't** bold everything — hierarchy dies.
- **Do** keep line length ≤ ~42 characters for body. **Don't** fill the slide edge to edge.
