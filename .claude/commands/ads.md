# /ads — Meta Ads Management Hub

Full Meta Ads management from Claude Code. Uses the Graph API directly via Bash curl commands.

## Credentials
Read from `.env`:
```bash
source .env
# TOKEN = $META_ACCESS_TOKEN
# Primary account = act_1203879293795719 (ItsZacNielsen, AUD)
```

## Sub-commands

Run as: `/ads report` | `/ads optimize` | `/ads create` | `/ads copy [topic]` | `/ads audience` | `/ads pause [campaign_id]` | `/ads history`

---

## /ads report

Pull live performance data for all active campaigns. Always use `source .env` first to get the token.

### Steps

1. **Pull account-level insights (last 7d + last 30d)**
```bash
source .env
# Last 7 days
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/insights?fields=impressions,reach,clicks,spend,cpm,cpc,ctr,actions&date_preset=last_7d&access_token=$META_ACCESS_TOKEN"
# Last 30 days
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/insights?fields=impressions,reach,clicks,spend,cpm,cpc,ctr,actions&date_preset=last_30d&access_token=$META_ACCESS_TOKEN"
```

2. **Pull all campaigns with status**
```bash
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/campaigns?fields=id,name,status,objective,daily_budget,lifetime_budget,created_time&access_token=$META_ACCESS_TOKEN"
```

3. **Pull insights per ACTIVE campaign**
For each campaign with status=ACTIVE:
```bash
curl -s "https://graph.facebook.com/v21.0/{CAMPAIGN_ID}/insights?fields=campaign_name,impressions,reach,clicks,spend,cpm,cpc,ctr,actions,cost_per_action_type&date_preset=last_7d&access_token=$META_ACCESS_TOKEN"
```

4. **Display a clean report:**

```
📊 Meta Ads Report — [DATE]
Account: ItsZacNielsen (act_1203879293795719) | Currency: AUD

LAST 7 DAYS
───────────────────────────────
Spend:        $X.XX AUD
Impressions:  X,XXX
Reach:        X,XXX
Clicks:       X,XXX
CTR:          X.XX%
CPM:          $X.XX
CPC:          $X.XX

ACTIVE CAMPAIGNS
───────────────────────────────
[For each active campaign:]
▶ [Campaign Name]
  Objective: [OBJECTIVE]
  Spend (7d): $X.XX | (30d): $X.XX
  Impressions: X,XXX | Reach: X,XXX
  CTR: X.XX% | CPM: $X.XX | CPC: $X.XX
  Key actions: [list meaningful actions with values]
  Status vs benchmarks: [GREEN/YELLOW/RED per KPI]

PAUSED CAMPAIGNS
───────────────────────────────
[List paused campaigns with last known stats]

ASSESSMENT
───────────────────────────────
[2-3 sentences on overall health, what's working, what needs attention]
```

5. **Benchmarks for assessment:**
- CPM: GREEN < $12 | YELLOW $12-20 | RED > $20
- CTR: GREEN > 2% | YELLOW 1-2% | RED < 1%
- CPC: GREEN < $0.50 | YELLOW $0.50-2 | RED > $2
- Messaging blocks: flag if > 5% of messaging actions

6. **Update `data/ad_performance.json`** with the fresh data (append to performance_history array with date)

---

## /ads optimize

Analyse the active campaigns and ad sets for optimisation opportunities.

### Steps

1. Run `/ads report` first to get current data

2. **Pull ad set level data** for active campaigns:
```bash
source .env
curl -s "https://graph.facebook.com/v21.0/{CAMPAIGN_ID}/adsets?fields=id,name,status,targeting,daily_budget,optimization_goal,billing_event,bid_strategy&access_token=$META_ACCESS_TOKEN"
```

3. **Pull ad set insights:**
```bash
curl -s "https://graph.facebook.com/v21.0/{ADSET_ID}/insights?fields=adset_name,impressions,reach,clicks,spend,cpm,cpc,ctr,frequency,actions&date_preset=last_7d&access_token=$META_ACCESS_TOKEN"
```

4. **Pull individual ad creatives:**
```bash
curl -s "https://graph.facebook.com/v21.0/{ADSET_ID}/ads?fields=id,name,status,creative,insights{impressions,clicks,ctr,spend,cpm}&access_token=$META_ACCESS_TOKEN"
```

5. **Analyse against the META_ADS_PLAYBOOK.md rules:**
   - Is budget above $20/day minimum?
   - Is frequency > 3? (audience fatigue risk)
   - Are there ad sets with > $50 spend and 0 results? (kill candidates)
   - Is BOFU creative being shown to cold audiences? (wrong funnel stage)
   - What's the best-performing ad? What makes it different?

6. **Output specific, actionable recommendations:**
```
🔧 Optimisation Recommendations — [DATE]

PRIORITY 1 (do today):
• [Specific action] — [reason based on data]

PRIORITY 2 (this week):
• [Specific action] — [reason]

EXPERIMENTS TO RUN:
• [New test to try based on what's working]

WHAT'S WORKING (don't touch):
• [Campaign/ad performing well — leave alone]
```

---

## /ads create

Guided campaign creation wizard.

### Steps

1. **Ask Zac:**
   - What is the goal? (leads / engagement / reach / sales)
   - What audience? (cold interest / retargeting IG engagers / lookalike)
   - What budget? (daily AUD)
   - What creative? (existing reel to promote / new creative to build)
   - Which CTA type? (DM / link to page / lead form / follow)

2. **Map to campaign structure:**
   - Leads goal → OUTCOME_LEADS objective
   - DM goal → OUTCOME_ENGAGEMENT + Click to Message
   - Awareness/reach → OUTCOME_AWARENESS

3. **Generate the campaign creation payload:**
```bash
source .env
# Create campaign
curl -s -X POST "https://graph.facebook.com/v21.0/act_1203879293795719/campaigns" \
  -d "name=[CAMPAIGN_NAME]" \
  -d "objective=[OBJECTIVE]" \
  -d "status=PAUSED" \
  -d "special_ad_categories=[]" \
  -d "access_token=$META_ACCESS_TOKEN"
```

4. **ALWAYS create as PAUSED first.** Show Zac the campaign structure and ask for confirmation before activating.

5. **For targeting, use these proven audience structures from META_ADS_PLAYBOOK.md**

---

## /ads copy [topic]

Generate Meta ad copy for a given topic using proven frameworks from META_ADS_PLAYBOOK.md.

### Steps

1. Read the ICA profile from `knowledge/ica_profile.md`
2. Read the META_ADS_PLAYBOOK.md copy frameworks (PAS, AIDA, Before/After/Bridge)
3. Generate 3 variations for the given topic:

**Output format:**
```
📝 Ad Copy: [TOPIC]

--- VARIATION 1: PAS ---
[Problem]
[Agitate]
[Solution]
[CTA]
Character count: XXX

--- VARIATION 2: AIDA ---
[Attention line]
[Interest]
[Desire]
[Action]
Character count: XXX

--- VARIATION 3: Before/After/Bridge ---
Before: ...
After: ...
Bridge: ...
CTA: ...
Character count: XXX

HOOK OPTIONS (for video overlay):
1. [Hook A]
2. [Hook B]
3. [Hook C]

RECOMMENDED: Variation X — because [specific reason based on current campaign objective]
```

---

## /ads audience

Audit current targeting and suggest improvements.

### Steps

1. Pull all ad sets with targeting data:
```bash
source .env
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/adsets?fields=id,name,status,targeting,reach_estimate&access_token=$META_ACCESS_TOKEN"
```

2. Review targeting against META_ADS_PLAYBOOK.md audience profiles

3. Check if custom audiences exist:
```bash
curl -s "https://graph.facebook.com/v21.0/act_1203879293795719/customaudiences?fields=id,name,subtype,approximate_count&access_token=$META_ACCESS_TOKEN"
```

4. **Output:**
   - Current audiences in use
   - Audience size estimates
   - Gaps (e.g. "No IG engager retargeting audience found")
   - Recommended audiences to build
   - Recommended lookalikes when pixel has enough data

---

## /ads pause [campaign_id]

Pause a specific campaign.

```bash
source .env
curl -s -X POST "https://graph.facebook.com/v21.0/[CAMPAIGN_ID]" \
  -d "status=PAUSED" \
  -d "access_token=$META_ACCESS_TOKEN"
```

Confirm before executing. Show campaign name and current spend first.

---

## /ads history

Show historical performance trend from `data/ad_performance.json`. If limited history exists, note it and suggest running `/ads report` regularly to build the dataset.

---

## General Rules
- **Never activate a campaign without showing Zac the full config and asking for confirmation**
- **Always source .env** — never hardcode the token
- **Reference META_ADS_PLAYBOOK.md** for all strategic decisions (budgets, targeting, creative formats)
- **Flag anomalies immediately** — messaging blocks > 10, CTR < 0.5%, CPM > $25 AUD
- **Current primary account:** `act_1203879293795719` (ItsZacNielsen, AUD)
