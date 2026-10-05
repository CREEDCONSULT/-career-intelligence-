# Color Palette — Career Intelligence (Dark Dashboard)

A dark, executive, analytical system. Gold is the signature. Blue = data/AI. Green = validation.
Red is rare and only ever a warning.

## Core tokens
| Role | Hex | Use |
|------|-----|-----|
| Background (deep) | `#071018` | page / slide background |
| Card background | `#0B1520` | primary cards |
| Card background alt | `#111C2A` | nested / secondary cards |
| Border / grid line | `#29384C` | 1px borders, grid overlay, dividers |
| **Gold accent** | `#D5B56E` | signature accent, labels, key underlines, "you are here" |
| Cream text | `#F7F1E8` | titles, primary text |
| Muted slate text | `#AEB9C8` | body, secondary text, captions |
| Data / AI blue | `#7CB4FF` | AI layer, data highlights, links |
| Validation green | `#8EE0B2` | success, "grounded", ticks, passing metrics |
| Warning red | `#FF9A9A` | *only* for risk/unverified — use sparingly |

## Supporting tints (for fills, chips, glows — keep subtle)
| Token | Value | Use |
|-------|-------|-----|
| Gold glow | `rgba(213,181,110,0.14)` | ghosted orb, pill fills, key-card wash |
| Blue wash | `rgba(124,180,255,0.12)` | AI-block fill, data chips |
| Green wash | `rgba(142,224,178,0.14)` | success chips, tick backgrounds |
| Red wash | `rgba(255,154,154,0.12)` | warning chip fills only |
| Card top-sheen | `rgba(255,255,255,0.03)` | 1px inner top highlight on cards |

## Usage ratios (the "60-30-10" for this system)
- **~70%** dark background + cards (`#071018` / `#0B1520` / `#111C2A`).
- **~20%** text (cream titles, slate body).
- **~10%** accents, of which **gold leads** and blue/green support. Red is <1%.

## Rules
1. **One accent leads per slide.** Usually gold. Blue when the slide is about the AI/data layer. Never a rainbow.
2. **Green means "verified / passing," not decoration.** If it's not a trust signal, don't use green.
3. **Red is an alarm, not a color.** Only unverified / warning / risk. A slide with red should be *about* risk.
4. **Contrast floor:** body text (`#AEB9C8`) on `#0B1520` passes; never put slate on `#071018` for long text — lift to cream.
5. **Gold is precious.** Underlines, one key number, stage markers, the active roadmap node. Overusing gold kills the executive feel.

## Gradients (optional, restrained)
- Background vignette: radial from `#0B1520` (center) → `#071018` (edges).
- Ghosted orb: radial `rgba(213,181,110,0.16)` → transparent, ~40% slide width, blurred, behind content.
