# Career Intelligence Dashboard - Brand Research & Positioning

**Project:** Career Intelligence Dashboard (Project 2 of Portfolio PRD)  
**Date:** June 16, 2026  
**Status:** Strategic Foundation - Pre-Design

---

## 1. MARKET LANDSCAPE & COMPETITIVE ANALYSIS

### 1.1 Direct Competitors (Career Intelligence / Job Market Data)

| Competitor | Positioning | Strengths | Weaknesses | Visual Language |
|------------|-------------|-----------|------------|-----------------|
| **LinkedIn Economic Graph** | Enterprise B2B, exclusive data | Proprietary data, massive scale | Not accessible, no public dashboard, expensive | Corporate blue, safe, dense |
| **Indeed Hiring Lab** | Public research arm, trend reports | Free data, credible, Toronto/Ontario data | Static reports, no interactive dashboard, limited skill granularity | Indeed brand (blue/orange), utilitarian |
| **Glassdoor** | Salary + reviews + jobs | Salary transparency, reviews | API deprecated, scraping risk, US-centric | Green/white, consumer-grade |
| **Levels.fyi** | Tech compensation focus | Excellent data viz, community-driven | Tech-only, senior-heavy, no Toronto focus | Dark mode, technical, data-dense |
| **Salary.com / PayScale** | Traditional compensation data | Enterprise credibility | Expensive, static PDFs, not real-time | Corporate, dated, report-heavy |
| **Government Sources (Job Bank, StatsCan, LMIC)** | Public good, authoritative | Free, legal, comprehensive, Toronto-specific | Raw CSVs, no viz, no skill extraction, monthly lag | None (raw data) |

### 1.2 Adjacent Inspiration (Data Products for Professionals)

| Product | Domain | Why Relevant |
|---------|--------|--------------|
| **Linear** | Issue tracking | Dark-mode-native, precision, developer-trusted, data-dense but clean |
| **Vercel** | Deployment platform | Minimal, shadow-as-border, workflow colors, text-as-infrastructure |
| **Stripe** | Payments/Financial | Blue-tinted shadows, weight-300 luxury, financial-grade trust, precise |
| **Notion** | Knowledge management | Warm minimalism, serif headings, soft surfaces, approachable density |
| **Superhuman** | Email client | Premium dark UI, keyboard-first, purple glow, speed-obsessed |
| **Raycast** | Launcher/productivity | Dark chrome, gradient accents, developer-native, polished |

---

## 2. TARGET AUDIENCE & USER PERSONAS

### 2.1 Primary Buyer (Consulting Context)
**Title:** VP Operations / VP Customer Success / COO  
**Company:** Toronto mid-market ($5M-200M revenue)  
**Pain:** "My team spends 20+ hrs/week on repetitive work. We tried ChatGPT/Zapier internally - couldn't make it production-grade."  
**Buys:** Evidence that you can turn raw data to pipeline to analysis to presentation  
**Evaluates:** Case studies with real numbers, architecture diagrams, methodology transparency

### 2.2 Direct User (Dashboard Context)
**Title:** Job Seeker / Career Changer / Hiring Manager / Recruiter  
**Goal:** Make high-stakes career decisions on data, not anecdotes  
**Needs:**
- Which skills are spiking in Toronto right now?
- What's the real salary range for [role] in Toronto?
- Am I competitive for [role cluster] - what's my gap?
- Is the market trending up or down for my target?

### 2.3 Influencer/Amplifier
**Title:** Technical evaluator (CTO, Senior Eng) / LinkedIn network  
**Role:** Validates technical credibility, shares content  
**Values:** Clean code, honest about limitations, reproducible methodology

---

## 3. POSITIONING STRATEGY

### 3.1 Core Positioning Statement

> **For Toronto job seekers and career professionals who make high-stakes decisions on anecdotal market data, Career Intelligence Dashboard is the only free, open-data-powered intelligence tool that turns 50,000+ monthly job postings into three actionable insights: which skills are spiking, what roles actually pay, and whether you're competitive - all built on transparent, reproducible methodology.**

### 3.2 Differentiation Pillars

| Pillar | Claim | Evidence |
|--------|-------|----------|
| **Data Integrity** | "Only tool using Job Bank + StatsCan + Indeed open data - no scraping, no ToS risk" | Open Government Licence, CC-BY-4.0, reproducible pipeline |
| **Toronto Specificity** | "Not national averages - Toronto CMA, economic region 3530, GTA municipalities" | Geographic filtering at municipal level |
| **Skill Granularity** | "NLP extraction from 50K+ posting requirements mapped to 34K Lightcast taxonomy" | Not NOC codes - actual skill mentions (Python, AWS, stakeholder management) |
| **Honest Methodology** | "We show you exactly how insights are derived - limitations included" | METHODOLOGY.md, confidence scores, data freshness timestamps |
| **Builder Credibility** | "Built by a consultant who ships production AI systems (CreedAI, Volatile, Ghost)" | Portfolio proves pipeline to product capability |

### 3.3 Brand Personality (Big Five + Voice)

| Dimension | Positioning | Manifestation |
|-----------|-------------|---------------|
| **Competence** | High - precise, engineered, trustworthy | Weight-300 headlines (Stripe), shadow-as-border (Vercel), blue-tinted depth (Stripe) |
| **Sophistication** | High - financial-grade, not consumer | Deep navy headings, conservative radii (4-8px), tabular numerals |
| **Approachability** | Medium - accessible to non-technical | Clear methodology expanders, plain-language insights, interactive role-fit |
| **Rigor** | Very High - reproducible, auditable | Monthly refresh logs, confidence intervals, source citations per insight |
| **Independence** | High - no platform dependency | Own data pipeline, deploy anywhere, open source |

**Voice Attributes:**
- **Precise:** "Q1 2026: 41,060 vacancies in Natural & Applied Sciences at avg $42.25/hr, down 8% YoY" - not "lots of tech jobs"
- **Transparent:** "Skill extraction confidence: 73% (limited by unstructured job requirement text)"
- **Actionable:** "Your gap: Cloud Architecture (demand +42% QoQ). Next step: AWS Solutions Architect Associate."
- **Restrained:** No hype words ("explosive," "skyrocketing," "revolutionary") - let data speak

---

## 4. VISUAL IDENTITY STRATEGY

### 4.1 Design System Lineage

Career Intelligence Dashboard sits at the intersection of three design lineages:

```
LINEAR (Precision)
  - Dark-mode-native, developer-trusted
  - Semi-transparent borders, luminance stacking
  - Inter Variable weight 510, aggressive tracking
       |
       v
CAREER INTELLIGENCE DASHBOARD
  - Light-mode primary (data clarity, accessibility)
  - Source Sans 3 weight 300 (Stripe luxury) + Geist Mono
  - Blue-tinted shadows (Stripe) + Shadow-as-border (Vercel)
  - Workflow accent colors for insight categories (Vercel)
       |
   +---+---+---+
   |         |         |
   v         v         v
STRIPE    VERCEL     NOTION
Financial  Workflow   Warmth &
grade      colors     Approach-
trust      for 3      ability
Blue tints  insights  Soft radii
```

### 4.2 Why Light Mode Primary?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Data Legibility** | Light | Tables, charts, sparklines read better on white; financial data tradition |
| **Accessibility** | Light | WCAG AAA easier; non-technical buyers expect light dashboards |
| **Trust Signal** | Light | "Financial institution" aesthetic - Stripe, banks, Bloomberg Terminal (light) |
| **Print/Share** | Light | Screenshots for LinkedIn posts, PDF exports, meeting presentations |
| **Dark Mode** | Optional | Developer preference toggle (localStorage persisted) |

### 4.3 Color Strategy: One Primary Accent + Three Insight Accents

**Primary Brand Accent:** Deep Indigo #3B2F9E  
- CTAs, primary navigation, brand marks, focus rings
- Trust, intelligence, depth - not the "SaaS purple" of Linear/Vercel

**Three Insight Category Accents** (inspired by Vercel's workflow colors):
| Insight View | Accent | Hex | Semantic Meaning |
|--------------|--------|-----|------------------|
| **Skill Demand** | **Growth Green** | #0FA958 | Growth, upward trend, "learn this" |
| **Salary Ranges** | **Wealth Gold** | #D4A80D | Compensation, value, negotiation |
| **Role Fit** | **Clarity Blue** | #0A72EF | Analysis, matching, "you fit here" |
| **Market Context** | **Signal Purple** | #7A4DFF | Macro trends, intelligence, synthesis |

---

## 5. BRAND ARCHITECTURE

### 5.1 Name: Career Intelligence Dashboard
- **Descriptive, not clever** - buyer knows what it is in 2 seconds
- **"Intelligence"** signals analysis, not just data - consultant positioning
- **"Dashboard"** = interactive, not static report

### 5.2 Tagline Options
1. *Toronto job market, decoded.* (Primary - concise, benefit-led)
2. *Where data meets decisions.* (Secondary - methodology emphasis)
3. *50,000 postings. 3 insights. 0 guesswork.* (Social - specific, credible)

### 5.3 Logo System
- **Wordmark:** "Career Intelligence" in Source Sans 3 weight 300, "Dashboard" in weight 400
- **Mark:** Abstract "CI" monogram - two overlapping columns (data) forming upward arrow (growth)
- **Favicon:** Single column + arrow at 32px
- **Usage:** Never smaller than 24px height; always with 2x clear space

---

## 6. COMPETITIVE VISUAL AUDIT SUMMARY

| Brand | Primary Font | Accent Approach | Shadow Philosophy | Border Radius | Trust Signal |
|-------|--------------|-----------------|-------------------|---------------|--------------|
| **Linear** | Inter Var 510 | Single indigo | Luminance stacking | 4-22px | Developer precision |
| **Vercel** | Geist 400/600 | 3 workflow colors | Shadow-as-border | 2-100px | Engineering minimalism |
| **Stripe** | sohne-var 300 | Purple + Ruby/Magenta gradients | Blue-tinted multi-layer | 4-8px | Financial luxury |
| **Notion** | Custom serif/sans | Warm coral | Soft, ambient | 4-12px | Approachable depth |
| **Superhuman** | Custom | Purple glow | Dark chrome | 4-8px | Premium speed |
| **Career Intel** | **Source Sans 3 (300/400) + Geist Mono** | **Deep Indigo + 3 insight accents** | **Blue-tinted + shadow-as-border hybrid** | **4-8px (conservative)** | **Financial-grade + analytic rigor** |

---

## 7. DESIGN PRINCIPLES (Decision-Making Framework)

1. **Data Clarity Over Decoration** - Every pixel earns its place; no decorative gradients, glassmorphism, or filler icons
2. **Financial-Grade Precision** - Tabular numerals, conservative rounding, blue-tinted shadows, deep navy text
3. **Methodology Transparency** - Insights show confidence, freshness, limitations; "Methodology" expander on every view
4. **Actionable Density** - High information density per viewport but scannable; No "data slop" (arbitrary metrics)
5. **Builder's Honesty** - "This pipeline runs monthly. Data lags 2-4 weeks. Skill extraction is 73% confident."
6. **Toronto First** - Geographic specificity visible in every label, filter, and footnote
7. **Portfolio-Grade Polish** - This IS the case study artifact; every interaction demonstrates craft

---

## 8. NEXT STEPS

1. **Formalize DESIGN.md token spec** (using design-md skill)
2. **Build component library** (buttons, cards, tables, charts, filters, badges)
3. **Create 3 dashboard view prototypes** (Skill Demand, Salary Ranges, Role Fit)
4. **Design "Methodology" expander pattern** (critical for buyer trust)
5. **Build interactive Role-Fit prototype** with Lightcast typeahead
6. **Generate LinkedIn-ready screenshots** with annotations
7. **Create one-page PDF case study** template

---

*This research informs the DESIGN.md token specification and all subsequent visual artifacts.*
