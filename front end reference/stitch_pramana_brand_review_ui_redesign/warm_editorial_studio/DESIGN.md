---
name: Warm Editorial Studio
colors:
  surface: '#fcf9f2'
  surface-dim: '#dcdad3'
  surface-bright: '#fcf9f2'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3ec'
  surface-container: '#f1eee7'
  surface-container-high: '#ebe8e1'
  surface-container-highest: '#e5e2db'
  on-surface: '#1c1c18'
  on-surface-variant: '#4e4635'
  inverse-surface: '#31312c'
  inverse-on-surface: '#f3f0e9'
  outline: '#807663'
  outline-variant: '#d1c5af'
  surface-tint: '#775a00'
  primary: '#775a00'
  on-primary: '#ffffff'
  primary-container: '#c59b27'
  on-primary-container: '#473500'
  inverse-primary: '#eec14b'
  secondary: '#5f5e61'
  on-secondary: '#ffffff'
  secondary-container: '#e4e1e6'
  on-secondary-container: '#656467'
  tertiary: '#7d562d'
  on-tertiary: '#ffffff'
  tertiary-container: '#c79768'
  on-tertiary-container: '#503009'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdf98'
  primary-fixed-dim: '#eec14b'
  on-primary-fixed: '#251a00'
  on-primary-fixed-variant: '#5a4300'
  secondary-fixed: '#e4e1e6'
  secondary-fixed-dim: '#c8c5ca'
  on-secondary-fixed: '#1b1b1e'
  on-secondary-fixed-variant: '#47464a'
  tertiary-fixed: '#ffdcbd'
  tertiary-fixed-dim: '#f0bd8b'
  on-tertiary-fixed: '#2c1600'
  on-tertiary-fixed-variant: '#623f18'
  background: '#fcf9f2'
  on-background: '#1c1c18'
  surface-variant: '#e5e2db'
typography:
  display-lg:
    fontFamily: Newsreader
    fontSize: 48px
    fontWeight: '400'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Newsreader
    fontSize: 36px
    fontWeight: '400'
    lineHeight: 44px
    letterSpacing: -0.015em
  display-md:
    fontFamily: Newsreader
    fontSize: 36px
    fontWeight: '400'
    lineHeight: 44px
    letterSpacing: -0.015em
  display-md-mobile:
    fontFamily: Newsreader
    fontSize: 28px
    fontWeight: '400'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 28px
    fontWeight: '500'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Newsreader
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 30px
    letterSpacing: -0.005em
  headline-sm:
    fontFamily: Newsreader
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0.005em
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.025em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 3rem
  margin-mobile: 1.25rem
  margin-tablet: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system is tailored for thoughtful literary review, craft writing environments, and editorial governance. The tone is deeply human, composed, disciplined, and intellectually trustworthy. It eschews hyper-synthetic visual tropes, artificial intelligence buzzwords, and decorative noise in favor of timeless print publishing traditions translated cleanly into digital form.

The design philosophy combines **Literary Minimalism** with **Warm Tactile Surfaces**:
- **Tone & Atmosphere:** Calm, deliberate, quiet, and erudite. Interactions feel like marking a manuscript with a fountain pen on heavy parchment.
- **Visual Style:** Warm, cream-tinted parchment backgrounds paired with dense charcoal ink typography. Visual boundaries rely primarily on tonal shifts and whisper-thin hairline separators rather than aggressive drop shadows.
- **Honesty in Communication:** The interface uses clear, direct language. Statuses are expressed plainly as verified text, conflicts, warnings, or notes without robotic jargon or exaggerated claims of computational infallibility.

## Colors

The palette mimics the physical tactility of an artisanal atelier: raw archival paper, dark carbon ink, and burnished gold leaf.

### Canvas & Surface Hierarchy
- **Base Canvas (`#faf8f5`):** The primary warm cream background for full-page views, creating an inviting paper-like ground.
- **Surface Level 1 (`#f5f2eb`):** Standard container surface, panel background, and structural card fill.
- **Surface Level 2 (`#ede8df`):** Interactive inputs, nested containers, hovered rows, and subtle inset wells.
- **Surface Charcoal (`#18181b`):** High-contrast editorial panels, primary buttons, and focal cards.
- **Deep Slate/Void (`#121214`):** Tooltips, floating contextual menus, and maximum-contrast display treatments.

### Ink & Text Tokens
- **Ink Primary (`#18181b`):** Deep charcoal for headlines, body copy, and essential iconography. Never pure `#000000`.
- **Ink Secondary (`#52525b`):** Muted carbon for secondary metadata, captions, and structural labels.
- **Ink Tertiary (`#71717a`):** De-emphasized timestamps, helper text, and subtle counters.
- **Hairline Border (`#e2dcd2`):** Soft, warm neutral border for card edges, dividers, and structural outlines.

### Semantic & Accent Logic
- **Editorial Amber / Gold (`#c59b27`, `#b8860b`, `#d4a373`):** Reserved exclusively for active selection states, key review action CTAs, and interactive focal points. It is not used to communicate positive resolution or task success.
- **Prohibited / Rule Violation (`#be4343`, surface `#fbf0ef`):** Muted crimson/rose for explicit rule breaks, editorial restrictions, and destructive options.
- **Warning / Factual Conflict (`#c58b27`, surface `#fcf6e8`):** Deep amber-ochre indicating conflicting references, stylistic deviations, or elements requiring manual cross-checking.
- **Verified / Clean Pass (`#3f624d`, surface `#edf4f0`):** Muted forest sage green, applied strictly when an automated verification pass has executed and yielded no conflicts.

## Typography

The typography pairing contrasts the warmth of literary publishing with the clarity of utilitarian editing tools.

- **Editorial Headlines (`Newsreader`):** Used for titles, article lead-ins, section headers, and manuscript excerpts. Its proportions provide a tangible bookish presence, offering optical grace and natural elegance. It is always set with generous vertical leading to honor traditional typesetting.
- **System Interface & Body (`Inter`):** Selected for high legibility across dense annotations, proofreading marks, sidebars, and control surfaces. `Inter` prevents eye strain during extended editing sessions and grounds the expressive serif titles with architectural precision.
- **Typographic Discipline:** Never italicize sans-serif metadata. Reserve italics solely for book titles, manuscript quotes, and deliberate editorial stress within serif text blocks. Uppercase styling is permitted strictly on `label-sm` tracking tags with expanded tracking (`0.04em`).

## Layout & Spacing

The layout adopts an editorial column architecture modeled on traditional broadsheet essays and review desks.

### Layout Model
- **Reading Canvas:** Central editorial body widths are constrained to a maximum of `68ch` (approximately `720px`) to preserve optimal line lengths for reading and focused editing.
- **Three-Tier Workspace Grid:** 
  - **Left Rail (Navigation & Outlines):** Fixed width of `260px` or collapsible drawer.
  - **Center Column (Draft & Document):** Fluid, occupying available room up to `840px` with generous auto-margins.
  - **Right Rail (Editorial Critique & Inspector):** Fixed width of `360px` dedicated to annotations, rule checks, and conflict reviews.
- **Gutters & Boundaries:** Multi-column layouts use `1.5rem` gutters on desktop and `1rem` on mobile devices.

### Breakpoints & Responsive Behavior
- **Desktop (≥ 1280px):** Simultaneous three-pane workspace visible without occlusion.
- **Tablet (768px – 1279px):** Document centered; inspector shifts into a right-aligned sliding sheet or toggleable docked panel. Gutters scale to `1.25rem`, canvas margins to `2rem`.
- **Mobile (< 768px):** Single-column layout. The inspector turns into a bottom sheet overlay accessible via a sticky review button. Primary canvas margin reduces to `1.25rem`.

## Elevation & Depth

Depth in this system is tactile, flat, and grounded. It is created through layered paper tiers and warm low-opacity ambient shadows rather than stark digital blurs.

### Surface Tiers & Hairline Edges
- **Flat Tiering:** Most container relationships use distinct background color variations (`#faf8f5` over `#f5f2eb`) separated by a crisp 1px border colored `#e2dcd2`.
- **No Heavy Drop Shadows:** Elevating cards with harsh black shadows contradicts the parchment aesthetic.

### Ambient Shadow Scale
- **Resting Level (`elevation-flat`):** No shadow. 1px solid border (`#e2dcd2`).
- **Raised Container (`elevation-low`):** Used for elevated cards, dropdown flyouts, and selectable notes.
  - `box-shadow: 0 1px 3px rgba(24, 24, 27, 0.04), 0 4px 12px rgba(24, 24, 27, 0.03);`
- **Floating Overlays (`elevation-high`):** Modals, manuscript comparison trays, and floating contextual toolbars.
  - `box-shadow: 0 4px 6px -1px rgba(24, 24, 27, 0.05), 0 16px 32px -4px rgba(24, 24, 27, 0.08);`
  - Paired with an extra-subtle backdrop tint (`rgba(24, 24, 27, 0.25)`) using minimal blur (`blur(2px)`).

## Shapes

The geometry of the interface embraces soft, well-tailored corners that feel comfortable to human touch without lapsing into toy-like softness.

- **Base Corner Radius (`0.5rem` / `8px`):** Applied to standard buttons, text inputs, status tags, list hovers, and table selections.
- **Large Corner Radius (`1rem` / `16px`):** Applied to content cards, editorial review panels, inspector trays, and modal dialogs.
- **Extra-Large Corner Radius (`1.5rem` / `24px`):** Applied exclusively to floating pillbars, central toolbar docks, and global navigation capsules.
- **Circular Elements:** Reserved strictly for avatars, status dot indicators, and icon-only round utility triggers.

## Components

### Buttons
- **Primary CTA (Editorial Focus / Review):** Solid deep charcoal (`#18181b`) background with cream text (`#faf8f5`). On hover, lightens to `#27272a`. Active states apply a subtle ring colored with warm amber (`#c59b27`).
- **Secondary / Action Button:** Warm cream surface (`#f5f2eb`), 1px border (`#e2dcd2`), and charcoal text (`#18181b`). On hover, surface shifts to `#ede8df`.
- **Accent Interactive CTA (Review / Resolve):** Warm gold (`#c59b27`) with dark charcoal text (`#18181b`). Reserved strictly for triggering reviews, resolving editorial conflicts, or initiating manuscript scans.
- **Ghost Button:** Transparent background, charcoal text. On hover, background fills with `#f5f2eb`.

### Chips & Semantic Status Badges
- **Default Editorial Chip:** Background `#ede8df`, text `#18181b`, border `#e2dcd2`, font `label-md`.
- **Prohibited Rule Badge:** Soft crimson background (`#fbf0ef`), deep crimson text (`#be4343`), hairline border (`#f3d2cf`).
- **Conflict & Warning Badge:** Pale ochre background (`#fcf6e8`), warm amber text (`#946400`), hairline border (`#eedab0`).
- **Verified Pass Badge:** Soft forest background (`#edf4f0`), deep sage text (`#2c523b`), hairline border (`#c8ded0`). Indicates a completed automated review with zero conflicts.

### Cards & Panels
- **Editorial Card:** Surface `#f5f2eb` bounded by a 1px `#e2dcd2` border. Padding `space-lg` (`1.5rem`). Headings utilize `headline-sm` or `headline-md` in `Newsreader`.
- **Active Review Focus Card:** Same base as the editorial card, augmented with a left accent border: 3px solid `#c59b27`.

### Input Fields & Search Bars
- **Text Inputs:** Surface `#faf8f5`, border 1px `#e2dcd2`, text `#18181b`, padding `0.75rem 1rem`. Typography `body-md`.
- **Focus State:** 1px border `#c59b27` combined with a soft outer ring: `0 0 0 3px rgba(197, 155, 39, 0.15)`. No cold blue outlines.
- **Placeholder Text:** Tone `#a19d95`.

### Lists & Manuscript Annotation Feeds
- **List Items:** Row items use subtle inset separation using hairline dividers (`#e2dcd2`). Hover state renders an effortless wash of `#f5f2eb`.
- **Annotation Callout:** Inset card with `#ede8df` fill, rounded `0.5rem`, containing a dual metadata header (`Inter` bold `label-sm`) and feedback critique text (`Inter` `body-sm`).

### Checkboxes & Radio Buttons
- **Base Style:** 18px square (or circle), 1.5px border `#d6cfc4`, background `#faf8f5`.
- **Selected State:** Fill `#18181b` with a crisp `#faf8f5` checkmark or center pip. Focus ring utilizes amber gold `rgba(197, 155, 39, 0.25)`.

### Manuscript Diff & Inline Highlights
- **Conflict Highlight:** Subtle background wash `rgba(197, 155, 39, 0.18)` beneath flagged sentences, accompanied by an amber dotted underline.
- **Prohibited Text Highlight:** Gentle rose background wash `rgba(190, 67, 67, 0.14)` with a red wavy underline.
- **Clean Pass Marker:** A compact inline tag (`label-sm`) displaying "Verified" in sage green text without visually disrupting the reading cadence.