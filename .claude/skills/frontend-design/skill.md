---
name: frontend-design
description: >
  Build distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics.
  Based on the Anthropic Claude Cookbooks frontend aesthetics guide.
  Triggers on: "design a page", "build a UI", "create a landing page", "make a dashboard",
  "build a component", "design a form", "create a frontend", /design, /frontend.
  Outputs working HTML/CSS/JS or React code with exceptional visual design.
---

# Frontend Design Skill

Build distinctive, production-grade frontend interfaces. Based on the
[Claude Cookbooks prompting_for_frontend_aesthetics](https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb) guide.

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design,
this creates what users call the "AI slop" aesthetic. Avoid this: make creative,
distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic
fonts like Arial and Inter; opt instead for distinctive choices that elevate the
frontend's aesthetics. Pair a distinctive display font with a refined body font.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency.
Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
Draw from IDE themes and cultural aesthetics for inspiration.

Motion: Use animations for effects and micro-interactions. Prioritize CSS-only
solutions for HTML. Use Motion library for React when available. Focus on
high-impact moments: one well-orchestrated page load with staggered reveals
(animation-delay) creates more delight than scattered micro-interactions.
Use scroll-triggering and hover states that surprise.

Spatial Composition: Unexpected layouts. Asymmetry. Overlap. Diagonal flow.
Grid-breaking elements. Generous negative space OR controlled density.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors.
Layer CSS gradients, use geometric patterns, or add contextual effects — gradient
meshes, noise textures, geometric patterns, layered transparencies, dramatic
shadows, decorative borders, grain overlays — that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts, Space Grotesk)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for
the context. Vary between light and dark themes, different fonts, different aesthetics.
Bold maximalism and refined minimalism both work — the key is intentionality, not intensity.
</frontend_aesthetics>

---

## Step 1 — Understand the context

Before writing any code, identify:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick a clear aesthetic direction — brutally minimal, maximalist, retro-futuristic,
  organic, luxury/refined, playful, editorial, brutalist, art deco, soft/pastel, industrial, etc.
- **Tech stack**: Plain HTML/CSS/JS? React? Vue? Tailwind?
- **Constraints**: Screen sizes, accessibility requirements, performance.
- **Differentiator**: What makes this UNFORGETTABLE? One thing someone will remember.

**CRITICAL**: Commit to the direction. Bold maximalism and refined minimalism both work —
the key is intentionality, not intensity.

---

## Step 2 — Design direction statement

Before coding, state in 2–3 sentences:
- The aesthetic direction chosen and why it fits the context
- The font pairing and why it was chosen
- The color palette and mood

Example:
> "Going with a brutalist editorial aesthetic — heavy black type on raw cream with sharp red
> accents. Syne + JetBrains Mono. Grid-breaking elements to feel like a printed magazine
> that learned to code."

---

## Step 3 — Implement the frontend

Write production-grade, functional code that:
- Uses Google Fonts (or system font stacks) for distinctive typography
- Defines a CSS custom property system (`--color-primary`, `--font-display`, etc.)
- Has orchestrated page load animations with `animation-delay` for staggered reveals
- Creates layered backgrounds (not solid colors)
- Is fully responsive

**For HTML output**: Self-contained single file with `<style>` and `<script>` inline.
**For React output**: Component file(s) using Tailwind or CSS modules.

---

## Step 4 — Review against the anti-patterns

Before presenting the code, check:
- [ ] No Inter/Roboto/Arial/Space Grotesk font families
- [ ] No purple gradient on white
- [ ] No flat solid background
- [ ] No scattered micro-interactions (one orchestrated moment is better)
- [ ] Asymmetry or visual interest in the layout (not just centered everything)
- [ ] CSS variables defined and used consistently

If any box is unchecked, revise before presenting.

---

## Elite Systems AI — Brand Context

When building UIs **for Zac's business** (elitesystems.ai, OperatorOS, internal tools,
client-facing pages), use these constraints:

**Brand colors:**
- Primary: `#0A0A0A` (near black)
- Accent: `#E8FF00` (electric yellow-green)
- Surface: `#111111`
- Text: `#F5F5F5`
- Muted: `#666666`

**Brand typography (preferred):**
- Display: `Clash Display` or `Cabinet Grotesk` (bold, geometric)
- Body: `DM Sans` or `Geist` (clean, readable)
- Mono: `JetBrains Mono` (for code/data)

**Brand aesthetic:** Dark, minimal, precise. Feels like a tool that works. Not a
marketing page — an operator's interface. Sharp edges, no rounded corners on primary
elements, strong typographic hierarchy.

**Elite Systems AI does NOT use:** Pastel colors, rounded pill buttons, gradient logos,
confetti animations, mascot illustrations.

---

## Rules

- Always state the design direction before writing code
- Single HTML file output by default unless React is specified
- Include Google Fonts `@import` or `<link>` for chosen fonts
- Every design must define a CSS custom property system
- If quality score < 8/10 after self-review, revise before presenting
- When in doubt: go darker, go bolder, go more specific
