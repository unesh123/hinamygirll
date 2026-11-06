# HINAA OS — Phase 19 Design Quality Rubric

## Objective Quality Evaluation
Phase 19 integrates an automated **Design Critic** (`DesignCritic.evaluate`) that grades generated and edited web applications on a 0–100 scale across 6 rigorous architectural and aesthetic dimensions.

To pass verification and be marked as `COMPLETED`, a project must achieve an overall score of **>= 85/100** with **zero critical visual or accessibility flaws**.

---

## The 6 Craftsmanship Dimensions

| Dimension | Weight | Target | Criteria & Standards |
|---|---|---|---|
| **1. Layout & Responsiveness** | 25% | >= 85 | Viewport meta tag present; fluid CSS grid/flexbox layouts; verified `@media` breakpoints at 1440px (Desktop), 768px (Tablet), and 390px (Mobile); no horizontal overflow. |
| **2. Typography & Hierarchy** | 20% | >= 85 | Clear typographic scale (h1 -> h2 -> p); line-height 1.4-1.7; modern web font imports (Inter, DM Sans, Plus Jakarta Sans, DM Serif); semantic hierarchy. |
| **3. Color Contrast & Palette** | 15% | >= 85 | WCAG AA minimum 4.5:1 contrast for normal text and 3:1 for large text; cohesive palette (background, surface, text, accent, border); no raw unstyled defaults. |
| **4. Interactivity & Affordance** | 15% | >= 85 | Interactive buttons have hover/focus states; active touch targets >= 44x44px; micro-interactions (toasts, modals, tabs) backed by DOM event listeners. |
| **5. Accessibility & Semantic HTML** | 15% | >= 80 | Semantic HTML5 structure (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`); `aria-label` on icon-only buttons; `alt` attributes on images. |
| **6. Nepali Cultural Fidelity** | 10% | >= 80 | Valid Devanagari Unicode support; Nepali typography font fallback (`Mukta`, `Noto Sans Devanagari`); authentic NPR currency symbols (रु.); realistic cultural content without generic tropes. |

---

## Negative Rules & Automatic Penalties

1. **Zero Lorem Ipsum Penalty (-25 pts)**:
   - Any occurrence of `"lorem ipsum"`, `"dolor sit amet"`, or generic filler text is penalized heavily.
   - All flagship missions and generated code must contain authentic, domain-specific copy.

2. **Missing Viewport Meta Tag (-30 pts)**:
   - Failing to include `<meta name="viewport" content="width=device-width, initial-scale=1">` causes immediate failure on mobile viewports.

3. **No Responsive Breakpoints (-20 pts)**:
   - CSS lacking `@media` queries fails the mobile and tablet responsiveness check.

4. **Missing Accessible Labels (-15 pts)**:
   - Buttons or interactive controls without text or `aria-label` trigger accessibility findings.
