# Career Intelligence Dashboard - Design System Quick Reference

## Color Palette (Copy-Paste Ready)

```css
:root {
  /* Primary Brand */
  --brand-primary: #3B2F9E;
  --brand-primary-hover: #4A3FC0;
  --brand-primary-light: #E8E5FC;
  
  /* Insight Accents (Semantic) */
  --accent-growth: #0FA958;      /* Skills */
  --accent-wealth: #D4A80D;      /* Salary */
  --accent-clarity: #0A72EF;     /* Fit */
  --accent-signal: #7A4DFF;      /* Context */
  
  /* Neutrals (Deep Navy base) */
  --neutral-975: #061B31;        /* Headings */
  --neutral-700: #273951;        /* Labels */
  --neutral-500: #64748D;        /* Body */
  --neutral-300: #B8BDC6;        /* Borders */
  --neutral-200: #E5EDF5;        /* Card borders */
  --neutral-100: #F0F4F8;        /* Subtle surfaces */
  --neutral-50:  #F7F9FC;        /* Alt background */
  --neutral-0:   #FFFFFF;        /* Cards */
  
  /* Shadows */
  --shadow-blue: rgba(50,50,93,0.25);
  --shadow-black: rgba(0,0,0,0.10);
  --border-shadow: rgba(0,0,0,0.08) 0px 0px 0px 1px;
  
  /* Focus */
  --focus-ring: 0px 0px 0px 3px rgba(59,47,158,0.4);
}
```

## Typography (CSS)

```css
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500&family=Geist+Mono:wght@400;500&display=swap');

:root {
  --font-primary: 'Source Sans 3', system-ui, sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, monospace;
}

.headline { font: 300 3.5rem/1.03 var(--font-primary); letter-spacing: -0.025em; font-feature-settings: "ss01"; }
.h1      { font: 300 2rem/1.10 var(--font-primary); letter-spacing: -0.02em; font-feature-settings: "ss01"; }
.h2      { font: 300 1.625rem/1.12 var(--font-primary); letter-spacing: -0.01em; font-feature-settings: "ss01"; }
.h3      { font: 300 1.375rem/1.10 var(--font-primary); letter-spacing: -0.01em; font-feature-settings: "ss01"; }
.h4      { font: 400 1.125rem/1.33 var(--font-primary); letter-spacing: -0.005em; font-feature-settings: "ss01"; }
.body-lg { font: 300 1.125rem/1.55 var(--font-primary); font-feature-settings: "ss01"; }
.body    { font: 400 1rem/1.5 var(--font-primary); font-feature-settings: "ss01"; }
.body-sm { font: 400 0.875rem/1.43 var(--font-primary); font-feature-settings: "ss01"; }
.caption { font: 400 0.8125rem/1.38 var(--font-primary); font-feature-settings: "ss01"; }
.mono    { font: 500 0.875rem/1.7 var(--font-mono); font-feature-settings: "liga", "tnum"; }
.micro   { font: 500 0.625rem/1.2 var(--font-primary); text-transform: uppercase; letter-spacing: 0.01em; font-feature-settings: "ss01"; }
```

## Component Patterns

### Insight Card (Growth/Skills)
```html
<div class="card card-growth">
  <h3 class="h3">Top Emerging Skills</h3>
  <p class="body-sm">Q1 2026 Toronto CMA</p>
  <div class="stat-value mono">+42%</div>
  <div class="data-meta">
    <span class="confidence-badge confidence-high">High Confidence</span>
    <span class="freshness-indicator">Updated Jun 3, 2026</span>
  </div>
</div>
```

### Methodology Expander (Required on Every View)
```html
<details class="methodology-expander">
  <summary class="methodology-trigger">
    Methodology
    <span class="icon">▼</span>
  </summary>
  <div class="methodology-content">
    <p>Skills extracted from 52,847 Toronto job postings (Job Bank Open Data, Jan-Mar 2026) using NLP against Lightcast 34K taxonomy. Confidence: 73% (limited by unstructured requirement text). Monthly refresh.</p>
  </div>
</details>
```

### Shadow Border Card (Vercel Technique)
```css
.card {
  background: white;
  border-radius: 6px;
  /* No CSS border! */
  box-shadow: 
    rgba(0,0,0,0.08) 0px 0px 0px 1px,     /* ring border */
    rgba(0,0,0,0.04) 0px 2px 4px -2px,    /* subtle lift */
    rgba(255,255,255,1) 0px 0px 0px 1px inset; /* inner highlight */
}
```

### Table with Tabular Numerals
```css
.table { font-feature-settings: "ss01", "tnum"; }
.table th { 
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.table td.numeric {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
```

## Insight Category System

| View | Accent | Top Border | Shadow Tint | Tab Color |
|------|--------|------------|-------------|-----------|
| Skills | #0FA958 | 3px solid | rgba(15,169,88,0.15) | green |
| Salary | #D4A80D | 3px solid | rgba(212,168,13,0.15) | gold |
| Fit | #0A72EF | 3px solid | rgba(10,114,239,0.15) | blue |
| Context | #7A4DFF | 3px solid | rgba(122,77,255,0.15) | purple |

## Spacing Scale

```css
:root {
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 20px; --space-6: 24px;
  --space-8: 32px; --space-10: 40px; --space-12: 48px;
  --space-16: 64px; --space-20: 80px; --space-24: 96px;
}
```

## Border Radius

```css
:root {
  --radius-sm: 4px;      /* buttons, inputs, badges */
  --radius-md: 6px;      /* cards, dropdowns */
  --radius-lg: 8px;      /* featured cards */
  --radius-pill: 9999px; /* status pills */
}
```

## Dark Mode (Optional Toggle)

```css
@media (prefers-color-scheme: dark) {
  :root {
    --neutral-0: #0F1011;
    --neutral-50: #191A1B;
    --neutral-100: #28282C;
    --neutral-200: #34343A;
    --neutral-300: #3E3E44;
    --neutral-500: #8A8F98;
    --neutral-700: #D0D6E0;
    --neutral-975: #F7F8F8;
    --border-shadow: rgba(255,255,255,0.08) 0px 0px 0px 1px;
    --shadow-black: rgba(0,0,0,0.3);
  }
}
```

## Assets to Create

- [ ] Logo mark (CI monogram + arrow) - SVG, 32px/64px/128px
- [ ] Favicon set (16, 32, 48, 192, 512)
- [ ] OG image template (1200x630) - branded, with insight preview
- [ ] Dashboard screenshots (3 views) - annotated for case study
- [ ] Architecture diagram (Mermaid to PNG)
- [ ] One-page PDF case study template
