# /post — Create Post + Add to Queue + Schedule via GHL

Interactive post creator. Takes content (or generates it), formats it for the chosen platform(s), adds it to the content queue, and schedules via GHL Social Planner.

## Usage
`/post` — interactive mode, Claude asks what you want to post
`/post [paste content here]` — format and schedule existing content

## Steps

### Step 1: Gather post details

If no content provided, ask:
1. **What's the topic?** (or paste the script/content directly)
2. **Which platform(s)?** (IG / LinkedIn / TikTok / X / Threads — pick one or multiple)
3. **What funnel stage?** (TOFU/MOFU/BOFU — or Claude determines from content)
4. **When to post?** (Today at [time] / Tomorrow at [time] / Specific date-time / Add to queue for Claude to suggest best slot)
5. **Media?** (Video link / image URL / text only)

All times in **Gold Coast/Brisbane AEST (GMT+10)**. No daylight saving.

### Step 2: Format content for each platform

Apply platform-specific formatting rules from `knowledge/brand_voice.md`:

**Instagram:**
- Caption: Hook line + 3-4 bullets + CTA + 7-8 hashtags
- Hashtag tiers: 2 broad + 3 mid + 2-3 niche
- Character check: first line under 125 chars (before "more" cutoff)

**LinkedIn:**
- No more than 5 hashtags (or none — test both)
- Line breaks matter: short punchy paragraphs
- End with a question or specific CTA

**TikTok:**
- Caption under 150 chars
- 3-5 hashtags max

**X/Twitter:**
- Under 280 chars for single tweet
- Or thread format if longer

**Threads:**
- Conversational, no hashtags needed

### Step 3: Determine best posting time

Gold Coast AEST (GMT+10, no daylight saving). Based on `knowledge/winning_patterns.md`:
- Best times: 7-9am AEST, 12-1pm AEST, 6-8pm AEST
- Best days: Tuesday, Wednesday, Thursday
- Check `data/content_queue.json` — avoid posting same day as another scheduled post
- Suggest an open slot in the calendar

### Step 4: Schedule via GHL (if configured)

Check if GHL credentials are in `.env` (`GHL_API_KEY` and `GHL_LOCATION_ID`).

**If configured:**
```bash
source .env
# Schedule post via GHL API
curl -s -X POST "https://services.leadconnectorhq.com/social-media-posting/posts" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Version: 2021-07-28" \
  -d '{
    "locationId": "'$GHL_LOCATION_ID'",
    "content": "[POST CONTENT]",
    "platforms": ["[PLATFORM]"],
    "scheduledAt": "[ISO DATETIME UTC]",
    "status": "scheduled"
  }'
```

Convert Gold Coast AEST to UTC: subtract 10 hours (no DST).

**If not yet configured:**
- Output formatted post ready to copy into GHL manually
- Remind: "Add GHL_API_KEY and GHL_LOCATION_ID to .env to enable auto-scheduling"

### Step 5: Update content queue

Add to `data/content_queue.json`:
```json
{
  "id": "[timestamp-based ID]",
  "topic": "[topic]",
  "platform": "[platform]",
  "funnel_stage": "TOFU/MOFU/BOFU",
  "cta_type": "follow/freebie/paid",
  "status": "scheduled/draft",
  "scheduled_at_aest": "YYYY-MM-DD HH:MM AEST",
  "scheduled_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "content_preview": "first 100 chars...",
  "ghl_post_id": "[if scheduled via API]"
}
```

### Step 6: Confirm

```
✅ POST SCHEDULED

Platform:    [Platform]
Funnel:      [TOFU/MOFU/BOFU]
When:        [Day, Date at Time AEST]
Status:      [Scheduled in GHL / Added to queue for manual scheduling]

CONTENT PREVIEW:
"[First line of post]..."

queue updated: data/content_queue.json ✓
[If GHL: "GHL Social Planner: scheduled ✓"]
[If manual: "Copy content above into GHL Social Planner"]
```
