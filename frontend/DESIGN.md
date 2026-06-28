---
name: Technical Precision
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006a61'
  on-secondary: '#ffffff'
  secondary-container: '#86f2e4'
  on-secondary-container: '#006f66'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#25005a'
  on-tertiary-container: '#9863ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#89f5e7'
  secondary-fixed-dim: '#6bd8cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#005049'
  tertiary-fixed: '#eaddff'
  tertiary-fixed-dim: '#d2bbff'
  on-tertiary-fixed: '#25005a'
  on-tertiary-fixed-variant: '#5a00c6'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-xl:
    fontFamily: Source Serif 4
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '450'
    lineHeight: 20px
  label-xs:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 24px
  margin-container: 32px
---

## Brand & Style
The design system is engineered for "promptuna," an LLM optimization tool that sits at the intersection of rigorous data science and cutting-edge AI development. The brand personality is academic, authoritative, and clinical, evoking the feeling of a high-end laboratory or a precision-engineered IDE.

The aesthetic follows a **Modern Technical** style—a hybrid of professional corporate clarity and developer-centric "Geek Chic." It utilizes high-contrast interfaces, sharp structural lines, and generous whitespace to reduce cognitive load during complex prompt engineering tasks. Subtle "fancy" technical flourishes, such as micro-monospaced labels and faint dot-grid backgrounds, reinforce the tool's specialized nature without sacrificing usability.

## Colors
The palette is rooted in a deep Slate Navy (`#0F172A`) to establish professional gravity. The background remains a crisp, sterile White (`#FFFFFF`) or an ultra-light Gray (`#F8FAFC`) to maximize legibility and emphasize data points.

Functional scoring colors—Green, Amber, and Red—are tuned for high visibility and accessibility against the light background. These are used strictly for performance metrics and trial results. Accents of Teal (`#0D9488`) and Purple (`#7C3AED`) are reserved for interactive elements and AI-specific features, signaling technical sophistication.

## Typography
The typography system creates a clear hierarchy by utilizing three distinct font classes:

- **Headlines (Source Serif 4):** A professional slab-serif that provides an authoritative, academic weight to the interface. It should be used for page titles and section headers.
- **Body Copy (Inter):** A systematic sans-serif designed for high-density information. This is the workhorse for instructions, descriptions, and general UI labels.
- **Technical/Data (JetBrains Mono):** A monospaced font used for all prompt text, LLM outputs, code snippets, and micro-labels. Its increased x-height ensures trial data is readable even at small sizes.

Micro-labels (labels-xs) should always be in JetBrains Mono and set in uppercase to differentiate metadata from UI actions.

## Layout & Spacing
The layout employs a **Fluid Grid** system based on a 4px baseline. This ensures all components align to a mathematical rhythm, reinforcing the technical nature of the product.

- **Desktop:** 12-column grid with 24px gutters. Use large margins (32px+) to maintain focus on the central prompt editing and data analysis areas.
- **Tablet:** 8-column grid with 16px gutters.
- **Mobile:** 4-column grid with 16px gutters.

Horizontal separators should be 1px solid lines to delineate sections without adding visual bulk. "Fancy" touches include subtle 16px x 16px dot-grid patterns in the background of empty states or sidebar panels.

## Elevation & Depth
This design system avoids heavy shadows, opting for **Tonal Layers and Low-Contrast Outlines**. Depth is established through the stacking of surfaces rather than physical light simulation.

- **Base Surface:** White (#FFFFFF).
- **Secondary Surface:** Slate-50 (#F8FAFC) for sidebars and secondary navigation.
- **Active Surface:** Slate-100 (#F1F5F9) for hover states or active card selections.
- **Borders:** 1px solid Slate-200 for standard containers. Use Slate-900 for high-contrast focus states.

Elevation is signaled by a transition from a 1px border to a subtle 2px solid border rather than a shadow, maintaining the "Sharp" and "Technical" aesthetic.

## Shapes
The shape language is strictly **Sharp (0px roundedness)**. This creates a precision-tool feel, echoing the aesthetics of vintage technical manuals and modern code editors.

Every UI element—from buttons and input fields to large cards and modal windows—must feature 90-degree corners. This uncompromising geometry ensures that the "Technical" narrative is consistent across the entire platform.

## Components
Consistent styling across components reinforces the precision-engineered feel:

- **Buttons:** Sharp corners. Primary buttons use the Slate-Navy background with white text. Ghost buttons use a 1px Slate-200 border. Labels are Inter (Medium) or JetBrains Mono for "Action" commands.
- **Input Fields (Prompt Editor):** Uses JetBrains Mono for the text area. The border is 1px Slate-200, turning 2px Slate-900 on focus.
- **Cards (Trial Data):** Sharp borders. Header of the card should use a subtle gray background (Slate-50) to separate metadata from the content body.
- **Chips/Scores:** Use a monospaced font (JetBrains Mono) for numerical values. Scoring chips use functional background colors (Green, Amber, Red) at 10% opacity with 100% opacity text for a "modern lab" look.
- **Lists:** Data-heavy lists should use alternating row stripes (Zebra striping) in Slate-50 to aid horizontal eye tracking across metrics.
- **Checkboxes/Radios:** Square (0px radius) even for radio buttons to maintain the brutalist, technical consistency.
