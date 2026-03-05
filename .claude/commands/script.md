# /script [topic] — Full Reel Script Generator

Write a complete, publish-ready reel script in Zac's voice with self-critique and revision loop.

## Usage
`/script AI agents for coaches`
`/script [topic]`
`/script [topic] [TOFU/MOFU/BOFU]` — optionally specify funnel stage

## Steps

### Step 1: Pre-script research
Before writing a single word:
1. Read `data/daily_content_brief.json` — is there an angle already researched for this topic? Use it.
2. Read `data/top_performing_content.json` — what hooks and formats have worked?
3. Read `knowledge/brand_voice.md` — tone rules, banned phrases, script structure
4. Read `knowledge/content_strategy.md` — what funnel type is needed? What's the daily target?
5. Determine funnel stage if not specified:
   - Trending news with strong take → TOFU (Format A)
   - Personal story / what I'm building → MOFU (Format B)
   - Myth bust / polarising opinion → TOFU/MOFU (Format C)
   - Deep system reveal → BOFU

### Step 2: Select the content format

Based on the topic and funnel stage, pick one of these three formats:

**Format A: Trending Reaction (TOFU)** — for breaking news or industry events
The hook states the TAKE, not the topic. Lead with opinion, not description.
```
Hook (0-3 sec):   "[Event] just happened. Here's what it actually means for your business:"
Reframe (3-13s):  "Everyone's saying [X]. That's the wrong take."
Your position (13-35s): "[Clear opinion + specific reasoning]"
Evidence (35-50s): "[Number, client result, or real example backing the position]"
CTA (50-60s):     "[Follow/Comment/DM] for [specific outcome]"
```

**Format B: Personal Story / Builder Documenting (MOFU)** — for what Zac is actually building
Makes content personal and credible. Use what's in Slack context if available.
```
Hook (0-3 sec):   "I'm building [specific thing] for a client right now."
Problem (3-13s):  "Their [specific pain] was [concrete description]."
System (13-40s):  "Here's how we fixed it: [3-step breakdown]"
Result (40-55s):  "[Specific metric or outcome — even if in progress]"
CTA (55-60s):     "Follow if you want to see the rest of this build."
```

**Format C: Myth Bust / Polarising (TOFU/MOFU)** — for taking a strong position against a common belief
```
Hook (0-3 sec):   "Unpopular opinion: [Bold claim]"
Setup (3-8s):     "Everyone says [common belief]."
The flip (8-35s): "Here's why that's wrong: [Your position + reasoning]"
Real answer (35-50s): "[What actually works]"
CTA (50-60s):     "[Follow/Comment] if you agree — or disagree, let me know"
```

### Step 3: Generate 5 hook options
Generate 5 hook options, all using the selected format as the base:
- Lead with the take/position in every option
- Vary the opening word: "Unpopular opinion:", "Hot take:", "I'm building...", "[Company] just did X.", "Everyone says X."
- No neutral hooks — every hook stakes a position

Score each hook 1-10 on: scroll-stop power, specificity, ICA relevance.

### Step 4: Write the full script

**Structure:** based on selected Format A, B, or C above
**Length:** 45–60 seconds at natural speaking pace (≈ 120-150 words)

**Voice rules (non-negotiable):**
- Write in first person — "I built", "my clients", "I disagree"
- One idea per sentence, each sentence on its own line
- Specific numbers always beat vague claims
- No "dive into", no "game-changer", no em dashes, no "let's explore"
- The script should sound like Zac texting a smart friend, not presenting to a room
**Format:**

```
[HOOK] (0-3 sec)
[one punchy line — the scroll stopper]

[PROBLEM] (3-8 sec)
[name the pain — make them say "that's me"]

[INSIGHT] (8-20 sec)
[the reframe — what most people miss]

[SYSTEM] (20-45 sec)
[the practical how — steps, tools, or framework]
[keep it specific enough to be credible, not so detailed it loses casual viewers]

[CTA] (45-60 sec)
[one clear action matching the funnel stage]
```

**Caption:**
```
[Restate hook as a declarative statement — makes them tap "more"]

• [Key point 1]
• [Key point 2]
• [Key point 3]

[CTA matching funnel stage]

[3 hashtags max — 1 broad + 1 mid + 1 niche. Never more than 3.]
```

### Step 4: Self-critique

Score the script on:
- Hook strength (1-10): Does it stop the scroll in 3 seconds?
- Voice match (1-10): Does it sound like Zac, not a generic AI content creator?
- ICA relevance (1-10): Would a coach/consultant/creator at 6-7 figures care?
- Structure clarity (1-10): Problem → Insight → System → CTA flow?
- Banned phrases check: Any "dive in", "unlock", "game-changer" etc?
- Funnel alignment (1-10): Does the CTA match the funnel stage?
- **Overall score (average)**

**If overall score < 8/10: rewrite automatically. Don't show the weak version.**

Identify the specific weaknesses, fix them, then present only the revised version with the score.

### Step 5: Final output

```
📱 SCRIPT: [TOPIC]
Funnel stage: [TOFU/MOFU/BOFU] | Pillar: [pillar name] | Length: ~XX words / ~XX seconds

HOOK SELECTED: [chosen hook]
Runner-up hooks:
  • [Hook 2]
  • [Hook 3]
  (say /hooks [topic] for all 5 with full analysis)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HOOK]

[PROBLEM]

[INSIGHT]

[SYSTEM]

[CTA]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CAPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Caption text]

[Hashtags]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUALITY SCORE: X.X/10
• Hook: X/10 — [note]
• Voice: X/10 — [note]
• ICA relevance: X/10 — [note]
• Structure: X/10 — [note]
• Funnel alignment: X/10 — [note]

FILMING NOTES:
• Format: [talking head / screen recording / text-overlay]
• B-roll suggestions: [what to show visually during each section]
• CTA visual: [what to show on screen during CTA]

Say /post to schedule this, or /hooks [topic] for more hook variations.
```
