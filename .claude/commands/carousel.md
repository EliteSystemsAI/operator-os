# /carousel [type] [topic] — Instagram Visual Content Generator

Generate slide-by-slide carousel scripts, quote post layouts, and comparison caricature image prompts for Instagram.

## Usage
- `/carousel personal [topic]` — Personal story carousel (MOFU/BOFU)
- `/carousel quote [topic]` — Single quote image layout (TOFU/MOFU)
- `/carousel comparison [topic]` — Comparison caricature (Some vs Others style)
- `/carousel batch` — Generate one of each type for the week

---

## Brand Aesthetic (apply to all carousel designs)

**Visual identity:**
- Background: `#0a0a0f` (near black — dark mode default)
- Surface/card: `#12121a`
- Border: `#1e1e2e`
- Primary accent: `#2563eb` (Elite Blue)
- Cyan highlight: `#00d4ff` (use sparingly)
- Text primary: `#f8fafc`
- Text secondary: `#94a3b8`
- Font: Inter (body), use bold weights for hooks/headlines
- Gradient CTAs: `linear-gradient(to right, #2563eb, #1e40af)`

**Format:**
- Instagram carousels: 1080 × 1080 px per slide
- Quote posts: 1080 × 1080 px or 1080 × 1350 px
- Comparison images: 1080 × 1350 px (two 1080 × 675 panels stacked)

---

## Type 1: Personal Story Carousel

### Purpose
Build personal brand. Show Zac as someone who lived the problem, built the solution, and now helps others do the same. MOFU (build loyalty) or BOFU (earn trust → lead).

### Structure (8 slides)

| Slide | Role | Content |
|---|---|---|
| 1 | Hook | Bold statement or relatable question. Must stop the scroll. |
| 2 | Context | Set the scene. Where Zac was. What the situation looked like. |
| 3 | Problem | The real pain. Be specific. Numbers help. |
| 4 | Turning point | The moment things changed. A decision, a realization, a build. |
| 5 | What changed | Concrete before/after. Specific outcomes. |
| 6 | The insight | The lesson. What this means for the reader. |
| 7 | Bridge | How this applies to their situation. |
| 8 | CTA | One clear action. Match to funnel stage. |

### Tone for personal carousels
- First person. Raw, not polished.
- Specific details (numbers, times, names of tasks)
- Never preachy — "I learned this the hard way" not "you need to do X"
- End on empathy: "If any of this sounds familiar..."

### Slide text rules
- Hook slide: 1 bold line + 1 subline max
- Body slides: 2–4 lines. Short sentences. Whitespace.
- No full paragraphs in slides — break every thought onto its own line
- CTA slide: Instruction + what they get

---

## Type 2: Quote Post

### Purpose
Standalone bold statement. Highly shareable. Good for TOFU reach or MOFU brand reinforcement.

### Design spec
- Full bleed dark background (`#0a0a0f`)
- Quote in large white Inter Bold, centered
- 1–2 line max for main quote
- Zac's handle ([YOUR_INSTAGRAM_HANDLE]) bottom right, small, muted grey
- Optional: thin Elite Blue left border accent
- Optional: small cyan glow behind text

### Quote formula
Choose one of:
- **Contrarian truth:** "[Popular belief] is wrong. [Real truth]."
- **Outcome statement:** "Your [thing] should [outcome]. If it doesn't, [implication]."
- **Permission statement:** "You don't need [what everyone says you need]. You need [real thing]."
- **Identity shift:** "Stop being [old identity]. Start being [new identity]."

### Output format
```
QUOTE POST
─────────────────
Quote:     "[the quote]"
Subtext:   "[optional second line — attribution or context]"
Handle:    [YOUR_INSTAGRAM_HANDLE]
Design:    Dark bg | white bold text | blue left accent
Funnel:    [TOFU/MOFU]
Caption:   "[Short caption. Restate quote. 1 CTA. 5-8 hashtags.]"
─────────────────
```

---

## Type 3: Comparison Caricature

### Purpose
"Some vs Others" style comic book image. High engagement, shareable, TOFU or MOFU.

### Character spec
- Athletic male, fitted black t-shirt, short styled brown hair swept to side, light stubble
- Same person in both panels
- NOT bald, NOT buzz cut, NOT different person

### Panel spec
- Final size: 1080 × 1350 px
- Top panel: 1080 × 675 (warm golden orange lighting — WINNING approach)
- Bottom panel: 1080 × 675 (cool blue-grey lighting — LOSING approach)
- No gap, no divider line between panels
- Text overlay after generation (white text, black stroke, bold, centered lower third)

### Image generation prompts

**Top panel (winning):**
```
Comic book illustration, cel shaded style, athletic male entrepreneur with short styled brown hair swept to the side, light stubble, fitted black t-shirt, [CONCRETE SCENE FOR SUCCESS]. Warm golden orange lighting, confident expression, clean modern office environment, rich detail, no text in image.
```

**Bottom panel (struggle):**
```
Comic book illustration, cel shaded style, same athletic male entrepreneur with short styled brown hair swept to the side, light stubble, fitted black t-shirt, [CONCRETE SCENE FOR STRUGGLE]. Cool blue-grey lighting, stressed exhausted expression, cluttered manual work environment, rich detail, no text in image.
```

### Scene translation rule
**NEVER use abstract phrases as scene descriptions.**
- BAD: "managing leads efficiently"
- GOOD: "sitting at a clean desk, laptop showing a CRM dashboard with green notification bubbles, phone propped up showing auto-reply confirmation"
- BAD: "struggling with manual processes"
- GOOD: "hunched over a cluttered desk, three browser tabs open, sticky notes covering the monitor, phone ringing in one hand, coffee spilled, dark circles under eyes"

### Minimal implementation flow
1. Translate topic into concrete scenes for each panel
2. Generate top panel image (use Higgsfield or equivalent)
3. Generate bottom panel image
4. Resize both to exactly 1080 × 675
5. Overlay text on each panel (lower third, white bold, black stroke)
6. Stack vertically: top first, bottom second
7. Export as PNG 1080 × 1350

### Quality checklist
- [ ] Character appears in BOTH panels
- [ ] Hair is short, styled, swept to side (not bald, not buzz cut)
- [ ] Top panel = warm and confident
- [ ] Bottom panel = cool and stressed
- [ ] Text meaning matches panel (not inverted)
- [ ] No black gap between panels
- [ ] No divider line
- [ ] Bottom panel is readable (2-3 specific struggle items, not chaotic)

---

## Output Format (all types)

```
CAROUSEL: [type] — [topic]
Funnel: [TOFU/MOFU/BOFU]
─────────────────────────────────

SLIDE 1 — [role]
[text]

SLIDE 2 — [role]
[text]

[...continue...]

SLIDE 8 — CTA
[text]

─────────────────────────────────
CAPTION:
[Full caption for the post]

HASHTAGS:
[7-8 niche hashtags]
─────────────────────────────────
```

---

## Step-by-Step for `/carousel batch`

1. Read `data/content_queue.json` to check what funnel stages are missing
2. Check `knowledge/content_strategy.md` for current week targets
3. Generate one of each: personal story carousel, quote post, comparison caricature
4. Assign funnel stage to each based on what's missing
5. Output all three with full slide content + captions
6. Ask if Zac wants to add to queue
