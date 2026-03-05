# /repurpose [url] — Video to 5-Platform Content

Take a YouTube video or existing reel and turn it into platform-native posts for IG, LinkedIn, TikTok, X, and Threads.

## Usage
`/repurpose https://youtube.com/watch?v=...`
`/repurpose [any video URL]`

## Steps

### Step 1: Extract content from the video

Use Playwright to navigate to the URL:

**For YouTube:**
1. Navigate to the video URL
2. Click "Show transcript" in the description area
3. Read the full transcript from the transcript panel
4. Also capture: title, description, approximate length

**For other video sources:**
- Try to read any available captions or transcript
- Use the title and description as context

### Step 2: Identify the core content

From the transcript, extract:
- The main topic/argument in one sentence
- The key insight or "aha" moment
- Any specific frameworks, steps, or systems mentioned
- Stats, numbers, or specifics worth preserving
- The hook moment (where does it get most interesting?)

### Step 3: Identify funnel stage
Based on the content depth and topic:
- Broad/educational → TOFU
- Personal/story-driven → MOFU
- Deep tutorial/system reveal → BOFU

### Step 4: Create 5 platform-native posts

**Platform 1: Instagram Reel (Script)**
- 45-60 second script adapted for the hook → problem → insight → system → CTA structure
- Include: caption + hashtags
- CTA matching funnel stage
- Note filming format (can they record a reaction/walkthrough or does original footage work?)

**Platform 2: LinkedIn Post**
- 400-600 words, professional tone
- Start with a bold statement (not "I am excited to share")
- Story arc: personal experience → lesson → system → takeaway
- End with a question to drive comments
- No hashtags (LinkedIn engagement drops with too many hashtags)

**Platform 3: TikTok Script**
- 30-45 seconds, faster pace than IG
- More casual, trend-aware if applicable
- Hook must be even more punchy — TikTok tolerance for slow starts is lower

**Platform 4: X/Twitter Thread**
- Tweet 1: Hook/bold claim (under 280 chars)
- Tweets 2-5: One key point each, tight
- Final tweet: CTA + summary
- Format: 1/ 2/ 3/ etc.

**Platform 5: Threads**
- Single post (Threads works best as conversation starter)
- Conversational, opinion-first
- 150-300 words
- Behind-the-scenes or "here's what I think about..." framing

### Step 5: Schedule to GHL (if confirmed)

If Zapier MCP is configured:
- Ask Zac: "Which platforms do you want to schedule? When?"
- Format each post for GHL Social Planner requirements
- Create scheduled posts via Zapier MCP/GHL API
- Update `data/content_queue.json`

If not yet configured: output posts as text ready to copy-paste manually.

### Step 6: Output

```
🔄 REPURPOSED CONTENT
Source: [URL]
Core topic: [one sentence]
Funnel stage: [TOFU/MOFU/BOFU]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 INSTAGRAM REEL SCRIPT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Full script]

Caption:
[Caption]
[Hashtags]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💼 LINKEDIN POST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Full LinkedIn post]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎵 TIKTOK SCRIPT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Script]
Caption: [Short caption]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐦 X/TWITTER THREAD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1/ [Tweet 1]
2/ [Tweet 2]
3/ [Tweet 3]
4/ [Tweet 4]
5/ [Tweet 5 — CTA]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧵 THREADS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Threads post]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Want to schedule these? Say /post to add them to the queue.
```
