---
name: slack
description: >
  Send Slack messages, reply to threads, and look up channels/users directly
  via the Slack API using the bot token from .env.
  Triggers on: "message [person] on Slack", "send to Slack", "update them on Slack",
  "let [person] know on Slack", "post in [channel]", "reply in Slack",
  "message the client", /slack.
  Never requires the Slack MCP OAuth plugin — uses SLACK_BOT_TOKEN directly.
---

# Slack Skill

Send messages to any Slack channel or user using the bot token already in `.env`.
No MCP plugin or OAuth flow needed.

---

## Tokens (from .env)

- `SLACK_BOT_TOKEN` — `xoxb-...` — use for all sends
- `SLACK_USER_TOKEN` — `xoxp-...` — use for user-scoped reads (search, history)

**IMPORTANT — sender identity:** Both tokens are tied to the EliteAnalyst Slack app.
Slack deprecated `as_user: true` in 2021 — it is now ignored. Messages will always
display as "EliteAnalyst" regardless of which token is used. There is no API workaround.
To change the display name, rename the app in api.slack.com/apps → App Name.

**If Zac asks to send "from me" or "as me":** Explain upfront that this is not possible
via the API. Instead, output the message text formatted for copy-paste so he can send it
directly in the Slack client. Do NOT attempt to send it — just produce the ready-to-send text.

Base URL: `https://slack.com/api`

---

## Known Channel IDs

| Channel | ID |
|---|---|
| #client-platypus-plants | `C09KEPSR0Q3` |
| #client-life-athlete-health | `C0AE4UGK01J` |
| #client-claim-safe-australia | `C09KQBU5RPW` |

Add to this table as you discover channel IDs.

---

## Step 1 — Resolve the destination

If the user specifies a channel name or person:
- Check the table above first
- If not found, resolve via API:
  ```bash
  curl -s "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" | python3 -c "
  import json,sys
  data = json.load(sys.stdin)
  for ch in data.get('channels', []):
      print(ch['id'], ch['name'])
  " | grep <name>
  ```
- For a DM to a person, find their user ID first:
  ```bash
  curl -s "https://slack.com/api/users.list" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" | python3 -c "
  import json,sys
  for u in json.load(sys.stdin).get('members', []):
      print(u['id'], u.get('real_name',''), u.get('name',''))
  " | grep -i <name>
  ```
  Then open a DM:
  ```bash
  curl -s -X POST https://slack.com/api/conversations.open \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"users": "<USER_ID>"}'
  ```
  Use the returned `channel.id` as the destination.

---

## Step 2 — Write the message

Write in Zac's voice: direct, warm, punchy. No fluff.

**Slack mrkdwn formatting:**
- Bold: `*text*`
- Bullet: `•` or `-`
- Code: `` `code` ``
- Link: `<url|text>`
- No `**`, no `##`, no markdown headers

**Tone for client updates:**
- Lead with the outcome, not the process
- Keep it to 3–5 lines max unless there's a list
- End with a clear next step or "let me know how it goes"

---

## Step 3 — Send the message

```bash
source /Users/ZacsMacBook/Documents/OperatorOS/.env

curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "<CHANNEL_ID>",
    "text": "<MESSAGE>"
  }'
```

Check `"ok": true` in the response. If false, check `"error"` field.

**To reply in a thread** (pass the parent message timestamp):
```bash
-d '{
  "channel": "<CHANNEL_ID>",
  "thread_ts": "<PARENT_TS>",
  "text": "<REPLY>"
}'
```

---

## Step 4 — Confirm

Report back:
- Channel or person the message was sent to
- First line of what was sent
- `ok: true` confirmation

---

## Reading recent messages (for context before replying)

```bash
curl -s "https://slack.com/api/conversations.history?channel=<CHANNEL_ID>&limit=20" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" | python3 -c "
import json,sys
msgs = json.load(sys.stdin).get('messages', [])
for m in reversed(msgs):
    print(m.get('ts'), m.get('user','bot'), ':', m.get('text','')[:120])
"
```

---

## Rules

- Always `source .env` before curl commands to pick up the token
- Use `SLACK_BOT_TOKEN` for all sends — bot appears as EliteAnalyst
- Never log or display the full token value in responses
- If `ok: false` and error is `not_in_channel`, invite the bot: `conversations.join`
- Update the Known Channel IDs table whenever a new channel is resolved
