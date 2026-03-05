# /trending — Deep AI Trend Analysis

Score and rank trending topics across 8 AI sub-categories to find the highest-opportunity content ideas right now.

## Steps

### Step 1: Search each sub-category
Use WebSearch to find what's trending across these 8 AI sub-categories. Search with today's date for recency.

| Category | Search queries |
|---|---|
| AI Tools & Releases | "new AI tool [date]", "AI tool launch [month year]" |
| LLM / Model News | "GPT Claude Gemini update [date]", "new AI model released [date]" |
| Automation / Workflows | "n8n Make Zapier workflow [date]", "business automation AI [date]" |
| Voice AI | "voice AI agent [date]", "ElevenLabs Vapi update [date]" |
| AI Agents | "AI agent autonomous [date]", "agentic AI business [date]" |
| No-Code AI | "no-code AI build [date]", "AI app builder [date]" |
| AI for Marketing | "AI content marketing [date]", "AI ads social media [date]" |
| AI Business Models | "AI freelance consultant [date]", "sell AI services [date]" |

### Step 2: Score each trend

For each notable trend found, score on 4 dimensions (1-10 each):

- **Recency** — How new is this? Breaking = 10, 1 week old = 6, 1 month old = 2
- **Engagement potential** — How much would this make the ICA stop scrolling?
- **ICA alignment** — How directly relevant to coaches/consultants/creators at scale?
- **Novelty** — Has this been covered to death already, or is there a fresh angle?

**Total score = average of 4 dimensions**

### Step 3: Identify contrarian opportunities

For the top 3 hype-heavy trends (high recency, lots of coverage), identify:
- What's the "real truth" that business owners need to know beyond the hype?
- What is everyone getting wrong or overstating?
- What's the practical implication for Zac's ICA specifically?

These become MOFU contrarian content opportunities.

### Step 4: Output the ranked list

```
🔥 TRENDING TOPICS — [DATE] (Gold Coast AEST)

RANK | TOPIC | SCORE | FUNNEL FIT | ANGLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#1 — [Topic name]
Score: X.X/10 (Recency: X | Engagement: X | ICA: X | Novelty: X)
Category: [AI sub-category]
What's happening: [1-2 sentences]
Best funnel stage: [TOFU/MOFU/BOFU]
Content angle: [Tutorial/Mythbust/Contrarian/etc]
Suggested hook: "[Draft hook line]"

#2 — [Topic name]
[same format]

... (continue for all scored topics)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTRARIAN OPPORTUNITIES (when hype > reality)

📌 [Hyped topic] — The real take:
"[What most people are saying]" vs "[What Zac should say as the grounded voice]"
Suggested hook: "[Contrarian hook]"
Funnel: MOFU — builds differentiation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEEKLY CONTENT PLAN SUGGESTION
Based on Stage 2 split (2 TOFU, 1 Double Down, 1 MOFU, 3 BOFU):

TOFU #1 (follow CTA):     #[N] — [topic]
TOFU #2 (freebie CTA):    #[N] — [topic]
DOUBLE DOWN:              [best previous post to remix]
MOFU (follow CTA):        [contrarian or personal angle]
BOFU #1 (follow CTA):     #[N] — [deep tutorial topic]
BOFU #2 (follow CTA):     #[N] — [system reveal topic]
BOFU #3 (paid offer CTA): #[N] — [authority/proof topic]

Say /script [topic] to write any of these.
```
