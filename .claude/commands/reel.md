# /reel — Latest Instagram Post Performance Analysis

Analyse the latest IG reel, save insights to the performance database, and get recommendations.

## Usage
`/reel` — analyses the most recent post on [YOUR_INSTAGRAM_HANDLE]
`/reel [instagram post URL]` — analyse a specific post

## Steps

### Step 1: Get the latest post

If no URL provided, use Playwright to navigate to instagram.com/itszacnielsen and find the most recent reel.

For the post, collect (from the page or URL):
- Post URL
- Caption text
- Approximate view count (if visible)
- Like count
- Comment count
- Date posted

### Step 2: Analyse the content itself (not just metrics)

Read the caption and any visible script/text. Evaluate against brand_voice.md and content_strategy.md:

**Hook Analysis:**
- What was the hook? (first line of caption or known from video)
- Which angle is it? (Tutorial/Mythbust/Transformation/Tip/Comparison/Contrarian)
- Hook score 1-10: scroll-stop power

**Script Structure:**
- Does it follow Problem → Insight → System → CTA?
- What funnel stage was it targeting? (TOFU/MOFU/BOFU)
- Was the CTA appropriate for that funnel stage?

**Topic Fit:**
- Which content pillar? (Tool Spotlight/System Reveal/Myth Busting/Results/How-To)
- ICA relevance score (1-10)

**Content Quality:**
- Any banned phrases used?
- Voice match (1-10)
- Depth appropriate for funnel stage?

### Step 3: Performance assessment

Compare metrics to benchmarks from `data/top_performing_content.json`:
- Views vs average
- Engagement rate = (likes + comments) / reach × 100
- Save rate (if available) — high saves = high perceived value
- Comment quality — are people asking questions? tagging others?

Flag: Above average / Average / Below average

### Step 4: Save to performance database

Update `data/top_performing_content.json`:
- Add post to the `posts` array
- Update `summary.total_posts_analysed`
- If above average: add hook pattern to `hook_patterns.high_performers`
- Update `topic_performance` and `format_performance` running averages

```json
{
  "post_url": "https://instagram.com/p/...",
  "date_posted": "YYYY-MM-DD",
  "caption_preview": "first 100 chars...",
  "funnel_stage": "TOFU/MOFU/BOFU",
  "pillar": "Tool Spotlight",
  "hook_angle": "Tutorial",
  "hook_text": "...",
  "format": "talking_head",
  "metrics": {
    "views": null,
    "likes": null,
    "comments": null,
    "saves": null,
    "engagement_rate": null
  },
  "quality_scores": {
    "hook": null,
    "voice": null,
    "ica_relevance": null,
    "structure": null
  },
  "performance_vs_average": "above/average/below",
  "notes": "..."
}
```

### Step 5: Output report

```
📊 REEL ANALYSIS
Post: [URL]
Date: [date posted]

METRICS
────────────────────────────────
Views:      [X,XXX] ([above/average/below] avg)
Likes:      [X] | Comments: [X] | Saves: [X]
Engagement: X.XX%

CONTENT ANALYSIS
────────────────────────────────
Funnel stage:  [TOFU/MOFU/BOFU]
Pillar:        [pillar]
Hook angle:    [angle]
Hook text:     "[hook]"
CTA type:      [follow/freebie/paid]
CTA matched funnel: [YES/NO]

QUALITY SCORES
────────────────────────────────
Hook strength:    X/10
Voice match:      X/10
ICA relevance:    X/10
Structure:        X/10
Funnel alignment: X/10

WHAT WORKED:
• [Specific observation]

WHAT TO IMPROVE:
• [Specific observation]

DATA SAVED: data/top_performing_content.json updated ✓

NEXT CONTENT SUGGESTION:
Based on this performance, [specific recommendation].
Say /script [suggested topic] to build it.
```
