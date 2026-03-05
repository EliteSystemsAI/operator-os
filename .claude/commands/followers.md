# /followers — Sync Instagram Follower Counts

Fetch current follower counts for Zac's Instagram accounts using browser automation, determine the current content strategy stage, and update `knowledge/content_strategy.md` with live data.

## Accounts to check
- Personal: instagram.com/itszacnielsen
- Business: instagram.com/elite.systemsai

## Steps

### 1. Open Instagram profiles in browser

Use Playwright browser tools. The **confirmed working method** (tested 2026-02-27):

Instagram's `og:description` meta tag is publicly readable before the login redirect fires. Navigate to the profile, then immediately evaluate the meta tag — don't wait for full page render.

For each account:
1. Navigate to `https://www.instagram.com/{handle}/`
2. Immediately run this JS evaluation (before redirect):
   ```
   () => { const og = document.querySelector('meta[property="og:description"]'); return og?.content || 'not found'; }
   ```
3. The meta content reads: `"1,097 followers, 1,193 following, 880 posts – see Instagram photos and videos from ..."`
4. Parse the follower count from the start of that string
5. Convert shorthand if present (e.g. "12.4K" → 12,400 / "1.2M" → 1,200,000)

### 2. Determine content strategy stage

Based on the **personal account** follower count ([YOUR_INSTAGRAM_HANDLE]), determine the stage:

| Followers | Stage | Priority |
|---|---|---|
| 0–1,000 | Stage 1 | Grow: TOFU-heavy |
| 1,000–10,000 | Stage 2 | Grow + Start converting |
| 10,000–100,000 | Stage 2+ | Convert: BOFU shift begins |
| 100,000–1,000,000 | Stage 3 | Convert: BOFU-heavy |

### 3. Calculate weekly posting split

**Stage 1 (0–1K):** 3 TOFU + 2 MOFU + 2 BOFU = 7/week
**Stage 2 (1K–10K):** 2 TOFU + 1 Double Down + 1 MOFU + 3 BOFU = 7/week
**Stage 3 (100K+):** 2 TOFU + 1 Double Down + 1 MOFU + 3 BOFU = 7/week (more BOFU paid CTAs)

### 4. Update content_strategy.md

Find the section at the bottom of `knowledge/content_strategy.md`:

```
## Zac's Current Stage
> **TODO:** Update with current follower count to apply correct posting split above.
```

Replace/update it with:

```markdown
## Zac's Current Stage
> Last updated: [TODAY'S DATE]

| Account | Handle | Followers |
|---|---|---|
| Personal | [YOUR_INSTAGRAM_HANDLE] | [COUNT] |
| Business | @elite.systemsai | [COUNT] |

**Active stage:** Stage [N] — [stage description]
**Weekly posting split:** [split summary]
**This week's priority:** [TOFU-heavy growth / BOFU-heavy conversion / balanced]
```

### 5. Output a summary

Display the result in a clean table:

```
📊 Follower Sync — [DATE]

[YOUR_INSTAGRAM_HANDLE]:     X,XXX followers
@elite.systemsai:   X,XXX followers

Current stage: Stage X ([description])
Weekly target: X TOFU | X MOFU | X BOFU
Priority CTA this week: [follow / freebie / paid offer mix]

knowledge/content_strategy.md updated ✓
```

## Error handling

- If Instagram blocks the page or requires login: note it in output and skip the update, but still show the last saved count from content_strategy.md
- If follower count shows as a shorthand (12.4K, 1.2M), convert to approximate integer for stage determination
- Don't update the file if the count couldn't be reliably read — show a warning instead
