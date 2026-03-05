# /hooks [topic] — Hook Generator & Analyser

Generate 5 high-scoring hook options across all angles, with scoring and a recommendation.

## Usage
`/hooks AI agents for coaches`
`/hooks [any topic]`

## Steps

### Step 1: Read context
- `knowledge/brand_voice.md` — hook formats that work, banned phrases
- `knowledge/winning_patterns.md` — which hook patterns get highest engagement in this niche
- `data/top_performing_content.json` — what has worked for Zac specifically

### Step 2: Generate one hook per angle

**Angle 1 — Tutorial**
Formula: "How to [specific result] in [specific timeframe/steps]"
Goal: Clear value promise, high completion rate, TOFU-friendly

**Angle 2 — Mythbust**
Formula: "Stop [common behaviour]. [Bold counter-claim]."
OR: "You don't need [thing everyone thinks they need]."
Goal: Pattern interrupt, triggers emotional response, MOFU/BOFU

**Angle 3 — Transformation**
Formula: "I went from [painful state] to [desired state] using [specific method]"
OR: "[Client] went from [X] to [Y] in [timeframe]"
Goal: Aspiration + proof, BOFU-friendly

**Angle 4 — Educational Tip**
Formula: "[Specific counterintuitive fact about AI/automation for business]"
OR: "Most [ICA role] don't know [specific thing]"
Goal: Curiosity + credibility, TOFU or BOFU depending on depth

**Angle 5 — Comparison / Contrarian**
Formula: "[Old way] vs [new way]: [specific difference]"
OR: "Everyone says [X]. Here's why that's wrong."
Goal: Debate-triggering, high comment volume, MOFU

### Step 3: Score each hook (1-10) on:
- **Scroll-stop power** — Would this make someone pause mid-scroll?
- **Specificity** — Is it concrete or vague?
- **ICA relevance** — Does a coach/consultant/creator at scale feel seen?
- **Curiosity gap** — Does it make them NEED to watch the next 5 seconds?

### Step 4: Output

```
🎣 HOOKS: [TOPIC]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOOK 1 — TUTORIAL
"[Hook text]"
Score: X.X/10 | Scroll-stop: X | Specificity: X | ICA: X | Curiosity: X
Best for: [funnel stage] | CTA: [follow/freebie/paid]
Note: [One sentence on why this works or doesn't]

HOOK 2 — MYTHBUST
"[Hook text]"
Score: X.X/10 | ...
[same format]

HOOK 3 — TRANSFORMATION
"[Hook text]"
Score: X.X/10 | ...

HOOK 4 — EDUCATIONAL TIP
"[Hook text]"
Score: X.X/10 | ...

HOOK 5 — CONTRARIAN
"[Hook text]"
Score: X.X/10 | ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ RECOMMENDED: Hook [N] — [one sentence reason]

Say /script [topic] to build a full script with this hook.
```
