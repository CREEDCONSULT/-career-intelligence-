---
version: alpha
name: Career Intelligence Dashboard
description: Financial-grade analytic rigor meets Toronto job market intelligence. Light-mode primary, blue-tinted depth, three insight accents, transparent methodology.
colors:
  # PRIMARY BRAND
  brand-primary: "#3B2F9E"
  brand-primary-hover: "#4A3FC0"
  brand-primary-light: "#E8E5FC"
  brand-primary-muted: "#6B5FCF"
  
  # INSIGHT CATEGORY ACCENTS (semantic, not decorative)
  accent-growth: "#0FA958"        # Skill Demand - growth, upward trend
  accent-growth-hover: "#12C966"
  accent-growth-light: "#E6F7EB"
  accent-growth-muted: "#2EB872"
  
  accent-wealth: "#D4A80D"        # Salary Ranges - compensation, value
  accent-wealth-hover: "#E8B812"
  accent-wealth-light: "#FEF3D6"
  accent-wealth-muted: "#C4970C"
  
  accent-clarity: "#0A72EF"       # Role Fit - analysis, matching
  accent-clarity-hover: "#1A84FF"
  accent-clarity-light: "#E8F0FE"
  accent-clarity-muted: "#2D8CFF"
  
  accent-signal: "#7A4DFF"        # Market Context - macro trends, synthesis
  accent-signal-hover: "#8D66FF"
  accent-signal-light: "#F0EBFF"
  accent-signal-muted: "#6B3DFF"
  
  # NEUTRALS (Deep Navy base - Stripe-inspired warmth)
  neutral-975: "#061B31"          # Primary headings - Deep Navy (NOT black)
  neutral-950: "#0D253D"          # Dark sections, footer
  neutral-900: "#171717"          # Body text fallback
  neutral-800: "#1E2A3A"
  neutral-700: "#273951"          # Labels, secondary headings
  neutral-600: "#4D4D4D"          # Tertiary text
  neutral-500: "#64748D"          # Body text - Slate
  neutral-400: "#8A8F98"          # Placeholder, metadata
  neutral-300: "#B8BDC6"          # Borders, dividers (light)
  neutral-200: "#E5EDF5"          # Card borders, input borders
  neutral-100: "#F0F4F8"          # Subtle surfaces, hover
  neutral-50: "#F7F9FC"           # Page background alt
  neutral-0: "#FFFFFF"            # Cards, pure white
  
  # SEMANTIC
  success: "#15BE53"
  success-text: "#108C3D"
  success-light: "rgba(21,190,83,0.15)"
  success-border: "rgba(21,190,83,0.3)"
  
  warning: "#D4A80D"
  warning-text: "#9B6829"
  warning-light: "rgba(212,168,13,0.15)"
  
  danger: "#EA2261"
  danger-text: "#C41A4D"
  danger-light: "rgba(234,34,97,0.15)"
  
  # SHADOW BLUE (Stripe-inspired chromatic depth)
  shadow-blue-strong: "rgba(50,50,93,0.25)"
  shadow-blue-medium: "rgba(50,50,93,0.15)"
  shadow-blue-subtle: "rgba(50,50,93,0.08)"
  shadow-black: "rgba(0,0,0,0.10)"
  shadow-black-strong: "rgba(0,0,0,0.15)"
  shadow-ambient: "rgba(23,23,23,0.06)"
  
  # VERCEL-STYLE SHADOW BORDERS
  border-shadow: "rgba(0,0,0,0.08) 0px 0px 0px 1px"
  border-shadow-light: "rgba(0,0,0,0.04) 0px 0px 0px 1px"
  border-focus: "rgba(59,47,158,0.4)"
  
  # OVERLAYS
  overlay-backdrop: "rgba(6,27,49,0.85)"
  overlay-light: "rgba(6,27,49,0.40)"
  
typography:
  font-family-primary: "Source Sans 3, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
  font-family-mono: "Geist Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace"
  font-feature-primary: ""ss01""
  font-feature-mono: ""liga", "tnum""
  
  display-hero:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "3.5rem"
    fontWeight: 300
    lineHeight: 1.03
    letterSpacing: "-0.025em"
    fontFeatureSettings: ""ss01""
  
  display-large:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "3rem"
    fontWeight: 300
    lineHeight: 1.15
    letterSpacing: "-0.02em"
    fontFeatureSettings: ""ss01""
  
  heading-1:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 300
    lineHeight: 1.10
    letterSpacing: "-0.02em"
    fontFeatureSettings: ""ss01""
  
  heading-2:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 300
    lineHeight: 1.12
    letterSpacing: "-0.01em"
    fontFeatureSettings: ""ss01""
  
  heading-3:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 300
    lineHeight: 1.10
    letterSpacing: "-0.01em"
    fontFeatureSettings: ""ss01""
  
  heading-4:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.33
    letterSpacing: "-0.005em"
    fontFeatureSettings: ""ss01""
  
  body-large:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 300
    lineHeight: 1.55
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  body:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  body-medium:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.50
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  body-small:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  caption:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.38
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  caption-small:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.33
    letterSpacing: "-0.03em"
    fontFeatureSettings: ""ss01", "tnum""
  
  micro:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 400
    lineHeight: 1.20
    letterSpacing: "0.01em"
    fontFeatureSettings: ""ss01""
    textTransform: "uppercase"
  
  mono-body:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.70
    letterSpacing: "0"
    fontFeatureSettings: ""liga""
  
  mono-caption:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.50
    letterSpacing: "0"
    fontFeatureSettings: ""liga", "tnum""
  
  mono-label:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.20
    letterSpacing: "0.02em"
    fontFeatureSettings: ""liga", "tnum""
    textTransform: "uppercase"
  
  button:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.00
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  button-small:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.00
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  link:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.00
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  nav-link:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.00
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  pill-badge:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.00
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""
  
  stat-value:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 300
    lineHeight: 1.00
    letterSpacing: "-0.02em"
    fontFeatureSettings: ""ss01", "tnum""
  
  stat-label:
    fontFamily: "Source Sans 3, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.30
    letterSpacing: "0"
    fontFeatureSettings: ""ss01""

rounded:
  micro: "2px"
  small: "4px"
  medium: "6px"
  large: "8px"
  xl: "12px"
  pill: "9999px"
  circle: "50%"

spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
  "6": "24px"
  "8": "32px"
  "10": "40px"
  "12": "48px"
  "16": "64px"
  "20": "80px"
  "24": "96px"
  "32": "128px"
  space-xs: "4px"
  space-sm: "8px"
  space-md: "16px"
  space-lg: "24px"
  space-xl: "32px"
  space-2xl: "48px"
  space-3xl: "64px"
  space-4xl: "96px"
  section: "80px"
  container: "1200px"

layout:
  container-max: "1200px"
  container-padding: "24px"
  sidebar-width: "280px"
  header-height: "64px"
  footer-height: "auto"
  grid-gap: "16px"
  grid-gap-sm: "8px"
  grid-gap-lg: "24px"
  sidebar-collapsed: "64px"
  sidebar-expanded: "280px"

elevation:
  flat:
    boxShadow: "none"
    backgroundColor: "{colors.neutral-0}"
  
  ring:
    boxShadow: "{colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
  
  card-subtle:
    boxShadow: "{colors.border-shadow}, {colors.shadow-black} 0px 2px 4px -2px"
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
  
  card:
    boxShadow: "{colors.shadow-blue-medium} 0px 12px 24px -12px, {colors.shadow-black} 0px 8px 16px -8px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
  
  elevated:
    boxShadow: "{colors.shadow-blue-strong} 0px 24px 48px -24px, {colors.shadow-black} 0px 12px 24px -12px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.large}"
  
  modal:
    boxShadow: "{colors.shadow-blue-strong} 0px 32px 64px -32px, {colors.shadow-black-strong} 0px 16px 32px -16px, {colors.border-shadow}, rgba(255,255,255,1) 0px 0px 0px 1px inset"
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.large}"
    backdropFilter: "blur(12px)"
  
  focus:
    boxShadow: "0px 0px 0px 3px {colors.border-focus}"
    outline: "none"
  
  card-growth:
    boxShadow: "rgba(15,169,88,0.15) 0px 12px 24px -12px, {colors.shadow-black} 0px 8px 16px -8px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderTop: "3px solid {colors.accent-growth}"
  
  card-wealth:
    boxShadow: "rgba(212,168,13,0.15) 0px 12px 24px -12px, {colors.shadow-black} 0px 8px 16px -8px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderTop: "3px solid {colors.accent-wealth}"
  
  card-clarity:
    boxShadow: "rgba(10,114,239,0.15) 0px 12px 24px -12px, {colors.shadow-black} 0px 8px 16px -8px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderTop: "3px solid {colors.accent-clarity}"
  
  card-signal:
    boxShadow: "rgba(122,77,255,0.15) 0px 12px 24px -12px, {colors.shadow-black} 0px 8px 16px -8px, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-0}"
    borderTop: "3px solid {colors.accent-signal}"
  
  inset:
    boxShadow: "{colors.shadow-black} 0px 0px 12px 0px inset, {colors.border-shadow}"
    backgroundColor: "{colors.neutral-100}"
    borderRadius: "{rounded.medium}"

components:
  btn-primary:
    backgroundColor: "{colors.brand-primary}"
    color: "#FFFFFF"
    borderRadius: "{rounded.small}"
    padding: "12px 20px"
    fontSize: "1rem"
    fontWeight: 400
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "none"
    cursor: "pointer"
    transition: "background-color 120ms ease, box-shadow 120ms ease"
  
  btn-primary-hover:
    backgroundColor: "{colors.brand-primary-hover}"
    boxShadow: "{colors.shadow-blue-medium} 0px 4px 12px -4px"
  
  btn-secondary:
    backgroundColor: "transparent"
    color: "{colors.brand-primary}"
    borderRadius: "{rounded.small}"
    padding: "12px 20px"
    fontSize: "1rem"
    fontWeight: 400
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.brand-primary-light}"
    cursor: "pointer"
    transition: "background-color 120ms ease, border-color 120ms ease"
  
  btn-secondary-hover:
    backgroundColor: "{colors.brand-primary-light}"
    borderColor: "{colors.brand-primary}"
  
  btn-ghost:
    backgroundColor: "transparent"
    color: "{colors.neutral-700}"
    borderRadius: "{rounded.small}"
    padding: "10px 16px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid transparent"
    cursor: "pointer"
    transition: "background-color 120ms ease, color 120ms ease"
  
  btn-ghost-hover:
    backgroundColor: "{colors.neutral-100}"
    color: "{colors.neutral-975}"
    borderColor: "{colors.neutral-300}"
  
  btn-insight-growth:
    backgroundColor: "{colors.accent-growth}"
    color: "#FFFFFF"
    borderRadius: "{rounded.small}"
    padding: "10px 18px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "none"
  
  btn-insight-growth-hover:
    backgroundColor: "{colors.accent-growth-hover}"
    boxShadow: "rgba(15,169,88,0.3) 0px 4px 12px -4px"
  
  btn-insight-wealth:
    backgroundColor: "{colors.accent-wealth}"
    color: "{colors.neutral-975}"
    borderRadius: "{rounded.small}"
    padding: "10px 18px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "none"
  
  btn-insight-wealth-hover:
    backgroundColor: "{colors.accent-wealth-hover}"
    boxShadow: "rgba(212,168,13,0.3) 0px 4px 12px -4px"
  
  btn-insight-clarity:
    backgroundColor: "{colors.accent-clarity}"
    color: "#FFFFFF"
    borderRadius: "{rounded.small}"
    padding: "10px 18px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "none"
  
  btn-insight-clarity-hover:
    backgroundColor: "{colors.accent-clarity-hover}"
    boxShadow: "rgba(10,114,239,0.3) 0px 4px 12px -4px"
  
  btn-insight-signal:
    backgroundColor: "{colors.accent-signal}"
    color: "#FFFFFF"
    borderRadius: "{rounded.small}"
    padding: "10px 18px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "none"
  
  btn-insight-signal-hover:
    backgroundColor: "{colors.accent-signal-hover}"
    boxShadow: "rgba(122,77,255,0.3) 0px 4px 12px -4px"
  
  card-default:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card}"
    border: "1px solid {colors.neutral-200}"
    padding: "{spacing.space-lg}"
  
  card-insight-growth:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card-growth}"
    border: "1px solid {colors.neutral-200}"
    padding: "{spacing.space-lg}"
    borderTopWidth: "3px"
    borderTopStyle: "solid"
    borderTopColor: "{colors.accent-growth}"
  
  card-insight-wealth:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card-wealth}"
    border: "1px solid {colors.neutral-200}"
    padding: "{spacing.space-lg}"
    borderTopWidth: "3px"
    borderTopStyle: "solid"
    borderTopColor: "{colors.accent-wealth}"
  
  card-insight-clarity:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card-clarity}"
    border: "1px solid {colors.neutral-200}"
    padding: "{spacing.space-lg}"
    borderTopWidth: "3px"
    borderTopStyle: "solid"
    borderTopColor: "{colors.accent-clarity}"
  
  card-insight-signal:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card-signal}"
    border: "1px solid {colors.neutral-200}"
    padding: "{spacing.space-lg}"
    borderTopWidth: "3px"
    borderTopStyle: "solid"
    borderTopColor: "{colors.accent-signal}"
  
  table-container:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.medium}"
    boxShadow: "{elevation.card-subtle}"
    border: "1px solid {colors.neutral-200}"
    overflow: "auto"
  
  table-head:
    backgroundColor: "{colors.neutral-50}"
    borderBottom: "1px solid {colors.neutral-200}"
  
  table-head-cell:
    padding: "12px 16px"
    textAlign: "left"
    fontWeight: 500
    fontSize: "0.75rem"
    textTransform: "uppercase"
    letterSpacing: "0.02em"
    color: "{colors.neutral-600}"
    fontFamily: "{typography.font-family-mono}"
    fontFeatureSettings: ""liga", "tnum""
  
  table-body-row:
    borderBottom: "1px solid {colors.neutral-200}"
    transition: "background-color 100ms ease"
  
  table-body-row-hover:
    backgroundColor: "{colors.neutral-50}"
  
  table-body-cell:
    padding: "12px 16px"
    color: "{colors.neutral-700}"
  
  table-body-cell-numeric:
    padding: "12px 16px"
    color: "{colors.neutral-700}"
    fontFamily: "{typography.font-family-mono}"
    fontFeatureSettings: ""liga", "tnum""
    textAlign: "right"
    fontVariantNumeric: "tabular-nums"
  
  input-default:
    backgroundColor: "{colors.neutral-0}"
    borderRadius: "{rounded.small}"
    border: "1px solid {colors.neutral-300}"
    padding: "10px 14px"
    fontSize: "1rem"
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    color: "{colors.neutral-975}"
    width: "100%"
    transition: "border-color 120ms ease, box-shadow 120ms ease"
  
  input-focus:
    borderColor: "{colors.brand-primary}"
    boxShadow: "0px 0px 0px 3px {colors.border-focus}"
    outline: "none"
  
  badge-default:
    backgroundColor: "{colors.neutral-100}"
    color: "{colors.neutral-700}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.neutral-300}"
    display: "inline-flex"
    alignItems: "center"
    gap: "6px"
  
  badge-growth:
    backgroundColor: "{colors.accent-growth-light}"
    color: "{colors.accent-growth}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.accent-growth-muted}"
  
  badge-wealth:
    backgroundColor: "{colors.accent-wealth-light}"
    color: "{colors.accent-wealth}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.accent-wealth-muted}"
  
  badge-clarity:
    backgroundColor: "{colors.accent-clarity-light}"
    color: "{colors.accent-clarity}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.accent-clarity-muted}"
  
  badge-signal:
    backgroundColor: "{colors.accent-signal-light}"
    color: "{colors.accent-signal}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.accent-signal-muted}"
  
  badge-success:
    backgroundColor: "{colors.success-light}"
    color: "{colors.success-text}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.success-border}"
  
  badge-neutral:
    backgroundColor: "transparent"
    color: "{colors.neutral-600}"
    borderRadius: "{rounded.pill}"
    padding: "4px 10px"
    fontSize: "0.75rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    border: "1px solid {colors.neutral-300}"
  
  nav-bar:
    backgroundColor: "{colors.neutral-0}"
    borderBottom: "1px solid {colors.neutral-200}"
    height: "{layout.header-height}"
    padding: "0 {layout.container-padding}"
    display: "flex"
    alignItems: "center"
    justifyContent: "space-between"
    position: "sticky"
    top: "0"
    zIndex: "100"
    backdropFilter: "blur(12px)"
    backgroundColor: "rgba(255,255,255,0.95)"
  
  nav-link:
    color: "{colors.neutral-600}"
    fontFamily: "{typography.font-family-primary}"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFeatureSettings: ""ss01""
    padding: "8px 12px"
    borderRadius: "{rounded.small}"
    textDecoration: "none"
    transition: "color 120ms ease, background-color 120ms ease"
  
  nav-link-active:
    color: "{colors.neutral-975}"
    backgroundColor: "{colors.neutral-100}"
    fontWeight: 500
  
  tabs-container:
    display: "flex"
    borderBottom: "1px solid {colors.neutral-200}"
    gap: "4px"
    padding: "0 {spacing.space-md}"
  
  tab:
    backgroundColor: "transparent"
    border: "none"
    padding: "12px 16px"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    color: "{colors.neutral-500}"
    borderBottom: "2px solid transparent"
    marginBottom: "-1px"
    cursor: "pointer"
    transition: "color 120ms ease, border-color 120ms ease"
  
  tab-active:
    color: "{colors.brand-primary}"
    borderBottomColor: "{colors.brand-primary}"
  
  methodology-expander:
    backgroundColor: "{colors.neutral-50}"
    border: "1px solid {colors.neutral-200}"
    borderRadius: "{rounded.medium}"
    padding: "{spacing.space-lg}"
    marginTop: "{spacing.space-lg}"
  
  methodology-trigger:
    display: "flex"
    alignItems: "center"
    justifyContent: "space-between"
    cursor: "pointer"
    padding: "4px 0"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    color: "{colors.neutral-700}"
  
  data-meta:
    display: "flex"
    alignItems: "center"
    gap: "{spacing.space-md}"
    fontSize: "0.75rem"
    color: "{colors.neutral-500}"
    fontFamily: "{typography.font-family-primary}"
    fontFeatureSettings: ""ss01""
    padding: "{spacing.space-sm} 0"
  
  confidence-badge:
    display: "inline-flex"
    alignItems: "center"
    gap: "4px"
    padding: "2px 8px"
    borderRadius: "{rounded.pill}"
    fontSize: "0.625rem"
    fontWeight: 500
    fontFamily: "{typography.font-family-mono}"
    fontFeatureSettings: ""liga", "tnum""
    textTransform: "uppercase"
  
  confidence-high:
    backgroundColor: "{colors.success-light}"
    color: "{colors.success-text}"
    border: "1px solid {colors.success-border}"
  
  confidence-medium:
    backgroundColor: "{colors.warning-light}"
    color: "{colors.warning-text}"
    border: "1px solid {colors.warning}"
  
  confidence-low:
    backgroundColor: "{colors.danger-light}"
    color: "{colors.danger-text}"
    border: "1px solid {colors.danger}"
  
  skeleton:
    background: "linear-gradient(90deg, {colors.neutral-100} 25%, {colors.neutral-200} 50%, {colors.neutral-100} 75%)"
    backgroundSize: "200% 100%"
    animation: "shimmer 1.5s infinite"
    borderRadius: "{rounded.small}"

motion:
  duration-fast: "120ms"
  duration-normal: "200ms"
  duration-slow: "300ms"
  easing-standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  easing-emphasized: "cubic-bezier(0.2, 0, 0, 1)"
  "@media (prefers-reduced-motion: reduce)":
    duration-fast: "0ms"
    duration-normal: "0ms"
    duration-slow: "0ms"

dos:
  - Use Source Sans 3 weight 300 for ALL headlines and body-large - lightness is the signature (Stripe principle)
  - Use weight 400 for body/UI, 500 for emphasis/navigation - never 600/700 on primary font
  - Enable "ss01" on ALL Source Sans 3 text - the geometric alternates define the brand
  - Enable "liga" + "tnum" on ALL Geist Mono text - ligatures and tabular numerals are structural
  - Apply blue-tinted shadows (rgba(50,50,93,...)) for elevation - chromatic depth ties to brand
  - Use shadow-as-border (0px 0px 0px 1px rgba(0,0,0,0.08)) instead of CSS borders on cards/inputs (Vercel principle)
  - Keep border-radius in 4px-8px range - conservative rounding signals financial precision
  - Use Deep Navy (#061B31) for headings instead of pure black - warmth matters
  - Apply negative letter-spacing at display sizes: -0.025em (56px), -0.02em (48px), -0.018em (40px), -0.01em (32px)
  - Use tabular numerals ("tnum") for ALL financial/data numbers - salary, vacancy counts, percentages
  - Layer shadows: blue-tinted far shadow + neutral near shadow + shadow-border ring
  - Use the three insight accents SEMANTICALLY: Growth Green (skills), Wealth Gold (salary), Clarity Blue (fit), Signal Purple (context)
  - Include "Methodology" expander on EVERY insight view - transparency builds buyer trust
  - Show data freshness timestamp and confidence badge on every data view
  - Use tabular numerals in stat values, tables, and chart tooltips
  - Respect prefers-reduced-motion - disable non-essential animation
  - Mobile hit targets minimum 44px - buttons, pills, tabs, inputs

donts:
  - Don't use weight 600-700 on Source Sans 3 - weight 300 is the brand voice (Stripe)
  - Don't use positive letter-spacing on display text - always negative or zero
  - Don't use pure black (#000000) for headings - always Deep Navy (#061B31)
  - Don't use neutral gray shadows - always tint with blue (rgba(50,50,93,...))
  - Don't skip "ss01" on Source Sans 3 - the alternate glyphs ARE the personality
  - Don't use large border-radius (12px+, pill) on cards/buttons - conservative 4-8px only
  - Don't apply insight accents decoratively - they are SEMANTIC category markers only
  - Don't use warm accent colors (orange, red, yellow) for interactive chrome - primary is Deep Indigo
  - Don't use CSS border property on cards/inputs - use shadow-border technique
  - Don't use heavy shadows (> 0.15 opacity) - the system is whisper-level
  - Don't introduce glassmorphism, gradient backgrounds, or decorative SVG illustrations
  - Don't add filler content - fake metrics, decorative stats, placeholder testimonials
  - Don't use emoji in UI chrome - typography and layout carry meaning
  - Don't make every section the same card grid - vary density and layout rhythm
  - Don't hide methodology behind clicks without clear affordance - expander must be obvious
  - Don't show data without freshness + confidence context - every view must have both

accessibility:
  contrast-ratio-body: "4.5:1"
  contrast-ratio-heading: "4.5:1"
  contrast-ratio-muted: "3:1"
  contrast-ratio-primary: "4.5:1"
  contrast-ratio-growth: "4.5:1"
  contrast-ratio-wealth: "3:1"
  contrast-ratio-clarity: "4.5:1"
  contrast-ratio-signal: "4.5:1"
  focus-visible: "3px solid border-focus"
  target-size-min: "44px x 44px"
  text-resize: "200% without horizontal scroll"
  prefers-reduced-motion: "honored"
  color-not-only-means: "status uses text + icon + color, never color alone"

exports:
  tailwind: "tailwind.theme.json"
  dtcg: "tokens.json"
  css-variables: "tokens.css"
  figma: "tokens.json (Figma Tokens plugin compatible)
