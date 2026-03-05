# /morning — Daily Content Briefing

Run this every morning to start the day with a clear content plan grounded in real data.

## Steps (run in order)

### Step 1: Sync follower counts
Run the `/followers` logic first:
- Navigate to instagram.com/itszacnielsen and instagram.com/elite.systemsai
- Extract follower counts from og:description meta tag
- Update `knowledge/content_strategy.md` if counts have changed

### Step 2: Check the content queue
Read `data/content_queue.json`:
- How many posts are scheduled this week?
- What funnel stages are covered?
- Are there gaps vs the Stage 2 target (2 TOFU, 1 Double Down, 1 MOFU, 3 BOFU)?

### Step 3: Read today's intelligence brief (check this FIRST before any web search)
Read `data/daily_content_brief.json`. If today's date matches the `date` field, use the `content_ideas` and `personal_context` from this file — the research agent already did the work.

If the brief is missing or stale (date doesn't match today), THEN fall back to web search:
- "AI news today [current date]"
- "AI automation business [current date]"
- "ChatGPT OpenAI announcement [current date]"

Focus on stories relevant to Zac's ICA: coaches, consultants, service businesses at $200K–$2M/year.

### Step 4: Cross-reference with content pillars + analytics
Read:
- `data/top_performing_content.json` — what formats/topics are performing? What's the best format right now?
- `knowledge/content_strategy.md` — what funnel stages are needed this week? What's today's 3-post target?
- `knowledge/content_pillars.md` — which pillar does each story fit?

### Step 5: Generate top 3 content opportunities

**IMPORTANT: Every opportunity must have a TAKE — a specific, polarising point of view. Not "here's what happened", but "here's what it actually means and my opinion on it."**

For each opportunity, output:
```
OPPORTUNITY #[N]
─────────────────────────────────
Story/Topic: [Specific topic or news event]
Funnel:    [TOFU / MOFU / BOFU]
Pillar:    [Which pillar, including Pillar 6: Breaking News]
Format:    [Reel / Carousel / Quote]
THE TAKE:  "[Your polarising opinion — one sentence, clear position]"
Hook:      "[Proposed opening line that leads with the take]"
Why now:   [Why this is timely]
Effort:    [Low / Medium / High — talking head / thread carousel / etc]
CTA:       [Follow / Comment X / DM me]
─────────────────────────────────
```

Also flag if there's a personal story from `personal_context` in the brief:
```
PERSONAL STORY OPPORTUNITY
─────────────────────────────────
From Slack: [what you're building]
Angle:      [how to frame it as a thread carousel]
Format:     Carousel — Tyler Germain thread style
─────────────────────────────────
```

Rank by: (timeliness × ICA relevance × polarising potential) — highest first.

### Step 6: Check ads (quick pulse)
Pull a quick 7-day snapshot from the primary Meta account:
```bash
source .env
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/insights?fields=spend,impressions,clicks,ctr,cpm&date_preset=last_7d&access_token=$META_ACCESS_TOKEN"
```

Flag anything outside benchmarks (CPM > $20 AUD, CTR < 1%, high messaging blocks).

### Step 7: Output the morning briefing

```
☀️ MORNING BRIEFING — [DATE, Gold Coast AEST]

📱 FOLLOWER UPDATE
[YOUR_INSTAGRAM_HANDLE]:   X,XXX (↑/↓ X from last check)
@elite.systemsai: XXX

📅 CONTENT QUEUE
This week: X/7 posts scheduled | Missing: [funnel stages needed]
[List scheduled posts with funnel stage]

🔥 TOP 3 CONTENT OPPORTUNITIES (each has a clear take — not just a topic)
[Opportunity #1 — full block]
[Opportunity #2 — full block]
[Opportunity #3 — full block]

📸 PERSONAL STORY FUEL
[If personal_context exists in brief, show it here: "From Slack: [what you're building] → carousel angle"]

📊 ADS PULSE (7 days)
Spend: $X.XX AUD | CTR: X.XX% | CPM: $X.XX | CPC: $X.XX
Status: [GREEN / YELLOW / RED] — [one-line note]

💡 TODAY'S RECOMMENDATION
Post type needed: [TOFU/MOFU/BOFU]
Best opportunity: Opportunity #[N] — [one sentence why]
Estimated time to create: [X mins] — [format]

Say /script [topic] to build the script for any opportunity above.
```
