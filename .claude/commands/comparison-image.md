# /comparison-image [topic] — Comparison Caricature Image Generator

Generate an Instagram comparison image in the "Some vs Others" comic book style.

## Usage
`/comparison-image [topic]`

Examples:
- `/comparison-image lead follow-up`
- `/comparison-image client onboarding`
- `/comparison-image business systems`

---

## Output Spec

- **Final size:** 1080 × 1350 px
- **Two panels stacked vertically, no gap, no divider line**
- Top panel: 1080 × 675 (winning approach)
- Bottom panel: 1080 × 675 (losing/manual approach)
- **Format:** PNG

---

## Character Spec (same male in both panels)

- Athletic build
- Fitted black t-shirt
- Short styled brown hair swept to the side
- Light stubble
- Friendly, confident face
- **NOT:** bald, buzz cut, long hair, different person between panels

---

## Visual Style

- Comic book, cel shaded, clean outlines
- **Top panel:** warm golden orange lighting, confident expression, clean modern office
- **Bottom panel:** cool blue-grey lighting, stressed/exhausted expression, cluttered environment (readable, not chaotic)

---

## Story Logic

- **Top = winning approach** — the smart/automated/systemised way
- **Bottom = losing approach** — the manual/exhausting/chaotic way
- Text meaning must match panel emotion — never invert

---

## Step-by-Step Implementation

### Step 1: Derive panel scenes from topic

Given the topic, translate into **concrete visual scenes**. Never use abstract business phrases.

Bad: "managing leads efficiently"
Good: "sitting relaxed at a clean desk with a laptop showing a dashboard, phone showing notification pings automatically"

Bad: "struggling with manual processes"
Good: "hunched over a desk buried in sticky notes and printed spreadsheets, three phones ringing at once, coffee spilled"

### Step 2: Build prompts

**Top panel prompt:**
```
Comic book illustration, cel shaded style, athletic male entrepreneur with short styled brown hair swept to the side, light stubble, fitted black t-shirt, [CONCRETE SCENE FOR SUCCESS]. Warm golden orange lighting, confident expression, clean modern office environment, rich detail, no text in image.
```

**Bottom panel prompt:**
```
Comic book illustration, cel shaded style, same athletic male entrepreneur with short styled brown hair swept to the side, light stubble, fitted black t-shirt, [CONCRETE SCENE FOR STRUGGLE]. Cool blue-grey lighting, stressed exhausted expression, cluttered manual work environment, rich detail, no text in image.
```

### Step 3: Generate images
- Use the image generation tool (Higgsfield or equivalent) to generate both panels
- Generate top panel first, then bottom panel

### Step 4: Resize and composite
- Resize both images to exactly 1080 × 675
- Stack vertically: top panel first, bottom panel second
- Zero gap between panels
- Export as PNG at 1080 × 1350

### Step 5: Add text overlays
- **White text, black outline stroke, bold**
- Centered in lower third of each panel
- Wrap lines for readability (max ~30 chars per line)
- Top panel text = winning/positive line
- Bottom panel text = losing/negative line

---

## Text Format Examples

**Topic: lead follow-up**
- Top: `AI follows up every lead\nwithin 60 seconds`
- Bottom: `Manually chasing leads\nfrom a spreadsheet`

**Topic: client onboarding**
- Top: `Client onboards themselves\nwhile you sleep`
- Bottom: `Sending welcome emails\none by one at 11pm`

---

## Quality Checklist (check before delivering)

1. ✅ Character appears in BOTH panels
2. ✅ Hair is correct (short, styled, swept to side — not bald/buzz cut)
3. ✅ Top panel is warm and confident
4. ✅ Bottom panel is cool and stressed
5. ✅ Text meaning matches panel meaning (not inverted)
6. ✅ No black gap between panels
7. ✅ No divider line
8. ✅ Bottom panel is not illegibly cluttered

---

## Common Failure Modes

| Failure | Fix |
|---|---|
| Different person in one panel | Add "same character as previous" to second prompt |
| One panel has no person | Rerun with explicit "male entrepreneur in foreground" |
| Hair wrong (buzz cut/bald) | Add "NOT bald, short styled brown hair, side-swept" to prompt |
| Text inverted (positive on bottom) | Re-check story logic before overlaying |
| Black padding between panels | Force exact pixel stitch with no border |
| Bottom panel unreadably cluttered | Dial back scene: 2-3 specific items, not "covered in everything" |

---

## Funnel Usage

This format works across all stages:
- **TOFU:** Broad comparison (e.g. "manual vs automated")
- **MOFU:** Relatable contrast (e.g. "before vs after systems")
- **BOFU:** Specific proof (e.g. "your current follow-up vs our system")

Always tag funnel stage and pair with appropriate CTA before posting.
