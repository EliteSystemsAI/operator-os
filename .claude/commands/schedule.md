# /schedule — View & Manage Content Calendar

Show the 14-day content calendar, flag gaps against the Stage 2 posting split, and suggest what to create next.

## Steps

### Step 1: Read the queue
Read `data/content_queue.json` to get all scheduled posts.
Read `knowledge/content_strategy.md` to get the current stage and weekly target.

### Step 2: Build the 14-day calendar view

For the next 14 days (from today, Gold Coast AEST), show each day's scheduled content (or "EMPTY").

### Step 3: Analyse the weekly split

For each of the 2 weeks:
- Count TOFU / MOFU / BOFU posts
- Compare to Stage 2 target: 2 TOFU + 1 Double Down + 1 MOFU + 3 BOFU = 7/week
- Check CTA mix: Does at least 1 TOFU have freebie CTA? At least 1 BOFU have paid offer CTA?
- Flag any days with 2 posts (over-posting risk)
- Flag any 2+ day gaps (momentum risk)

### Step 4: Output the calendar

```
📅 CONTENT CALENDAR — [DATE] (Gold Coast AEST)

WEEK 1: [DATE] to [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mon [date]: [TOFU/MOFU/BOFU] "[post title/topic]" | CTA: [type]
Tue [date]: [TOFU/MOFU/BOFU] "[post title/topic]" | CTA: [type]
Wed [date]: EMPTY ⚠️
Thu [date]: [TOFU/MOFU/BOFU] "[post title/topic]" | CTA: [type]
Fri [date]: [TOFU/MOFU/BOFU] "[post title/topic]" | CTA: [type]
Sat [date]: EMPTY
Sun [date]: EMPTY (rest day — stories only)

Week 1 split: X TOFU | X MOFU | X BOFU (target: 2/1/3)
Status: [✅ On track / ⚠️ Gaps: missing MOFU, BOFU #3]

WEEK 2: [DATE] to [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Same format]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAPS TO FILL
• [Date]: Need MOFU post — say /script [topic] to create one
• [Date]: Need BOFU with paid offer CTA — say /script [topic] BOFU

QUEUE HEALTH
Total scheduled: X posts
On-track to hit 7/week: [YES / NO — X short]

Say /post to add content, or /script [topic] to generate a script.
```

### Step 5: If queue is empty or near-empty

Trigger a mini-version of `/morning` to suggest what to create:
- Check what funnel stages are missing
- Suggest 2-3 specific topics from `knowledge/content_pillars.md`
- Recommend running `/trending` for fresh ideas
