# /notify [message] — Send Telegram Alert to Zac

Send a custom notification to Zac's Telegram. Use for reminders, alerts, or status updates from automated workflows.

## Usage
`/notify [your message]`

Examples:
- `/notify Content queue is empty — needs 3 BOFU scripts`
- `/notify New qualified lead just came in from IG DMs`
- `/notify Meta token expired — generate new one at developers.facebook.com`

## Steps

### Step 1: Send message via Telegram Bot API

```bash
source .env
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "'"$TELEGRAM_CHAT_ID"'",
    "text": "[MESSAGE]",
    "parse_mode": "Markdown"
  }'
```

### Step 2: Confirm delivery

Check response for `"ok": true`. If failed, report the error.

## Standard Alert Templates

### 🔥 Qualified Lead Alert
```
🔥 NEW QUALIFIED LEAD — IG DM

Name: [name]
Business: [type]
Revenue: [range]
Pain: [answer]
Ready: YES

View in GHL: [link]
```

### ⚠️ Action Required Alert
```
⚠️ ACTION NEEDED

[What needs doing]
[Why it's urgent]
[How to fix it]
```

### 📊 Daily Summary Alert
```
📊 DAILY SUMMARY — [DATE]

Content: [X posts scheduled this week]
Leads: [X new, X qualified]
Revenue MTD: $[X]
Ads: [status]

Top action: [one thing]
```

### 🔑 Token Expired Alert
```
🔑 META TOKEN EXPIRED

Generate new token:
1. developers.facebook.com/tools/explorer
2. App: Ad Optimisation
3. Permissions: ads_read, ads_management
4. Generate → copy → run /env update in Claude
```

## Notes
- Telegram Bot Token: stored in `.env` as `TELEGRAM_BOT_TOKEN`
- Chat ID: `7799457272` (Zac's personal chat)
- Messages support Markdown formatting
- Max message length: 4096 characters
