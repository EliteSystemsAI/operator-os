---
name: email
description: >
  Draft and send emails in Zac's voice directly into Gmail as drafts.
  Use when asked to: "draft an email", "send an email to", "write an email",
  "follow up with", "close the loop with", "reach out to", "reply to".
  Always creates Gmail drafts via MCP — never just outputs text for copy-paste.
---

# Email Skill

## Goal
Write emails in Zac's voice and create Gmail drafts directly so he only needs to review and hit send. Never output raw email text and ask Zac to copy-paste.

---

## Zac's Email Voice

**Core tone:** Australian, direct, warm, never salesy. Sounds like a mate reaching out — not a sales rep.

**Rules:**
- Short and sharp. Max 5–7 lines for outreach. If it needs scrolling, it's too long.
- Lead with relevance, not pitch. Why is this relevant to *them*, right now?
- Backfoot energy — don't chase. Make it easy to say yes or no without pressure.
- Each thought gets its own paragraph/line — no run-ons, no bullet points in outreach.
- Never say: "I hope this finds you well", "I wanted to reach out", "touching base", "circling back", "per my last email", "as discussed", "just checking in", "following up"
- Avoid: bullet points in outreach emails, long intros, feature lists, restating value when they've said no
- "flick me a message" = Zac's preferred casual CTA phrase
- Contractions and Australian-isms are encouraged: "all good", "no stress", "keen", "haha"

**Sales energy (IMPORTANT — applies to all proposal and follow-up emails):**
The core positioning: *we get back to people because we're busy too — not because we're chasing the sale.*

Zac doesn't chase leads. He solves problems. The person on the other end has a problem; Zac has the solution. That's the frame — confident, not arrogant.

This means:
- Never write like Zac is waiting on a reply. He's not.
- Never position a follow-up as "checking if you had a chance to look". He's circling back because the timeline makes sense, not because he's anxious.
- Never explain *why they should reconsider* after they've said not now. That's chasing.
- When reaching back out, lead with the trigger (a reason it's relevant *now*) — not with "just following up on my email."
- Proposals are not pitches. They solve a defined problem. The framing is: *"Here's what we heard, here's the cost of not solving it, here's the system we're building — does it land?"*
- Grand Slam Offer energy (from Alex Hormozi): make the offer so clearly matched to their problem that the decision is easy. Never compare against other vendors. Name the solution. Stack the value. Make inaction feel costly.

**Sign-off guide (IMPORTANT — these are exact patterns from actual sent emails):**
| Relationship | Sign-off |
|---|---|
| Personal friend / mate | `Cheers legend,\nZac` |
| Casual professional / warm lead | `Cheers,\nZac` |
| Warm exit / loop close | `All the best,\nZac` |
| Formal proposal / client document | `Best regards,\n\n[YOUR_NAME]\nDirector & AI Automation Consultant\nElite Systems AI` |
| NEVER use | "Stay inspired", just "Zac" alone, "Kind regards", "Warm regards" |

**Temperature guide:**
| Relationship | Tone |
|---|---|
| Personal friend (met multiple times) | Texting energy. One sentence per idea. "Cheers legend" sign-off. |
| Warm intro (met once or mutual connection) | Friendly but slightly structured. "Cheers" sign-off. |
| Cold/inbound lead | Direct but human. Acknowledge their situation first. |
| Existing client | Peer-to-peer. No fluff. Get to the point. |

---

## Email Types

### Warm Outreach (friend or mutual intro)
- 1 line: acknowledge the connection or what prompted the reach-out
- 1–2 lines: relevant hook (why this might matter for *them*)
- 1 line: low-pressure CTA (coffee, quick call, "if you're keen")

### Follow-up (they're thinking about it)
- Lead with a reason it's relevant *now* — a trigger, timeline, or new context. Never "just following up."
- Acknowledge where you left off (1 line max)
- Add new value or perspective if possible — if there's nothing new to say, don't send it yet
- Soft CTA — no pressure
- Energy: Zac is circling back because the timing makes sense, not because he's waiting on an answer

### Breakup / Loop Close
Two sub-patterns depending on context:

**Cold / no-reply (proposal sent, silence since):**
- "Closing the loop on [X] — been a couple of months now and haven't heard back."
- One line giving them an easy out: "No pressure either way. If timing's shifted, all good."
- One line leaving door open: "Just flick me a message and let me know."
- Sign-off: "Cheers, Zac"
- 3–4 lines total

**Warm / they said not now (had meetings, then backed out):**
- Acknowledge what they said — one line, no pushback, no restating value
- "Makes sense to hold off if [their reason] isn't quite there yet."
- Leave the door open: "When things shift, just reach out and we'll pick it back up."
- Sign-off: "All the best, Zac"
- 3 lines max — do NOT re-sell, do NOT explain why they should reconsider

### Proposal Send
- Thank them for the call (1 line, optional — skip if it was weeks ago)
- Name the solution product, not the tools: "The [Name] System" not "an n8n workflow"
- Point to the proposal + 1-line summary of what it solves (the problem, not the features)
- Clear next step — specific and friction-free
- Do NOT compare against other vendors or platforms — position the solution on its own terms
- Grand Slam Offer energy: the proposal already does the heavy lifting. The email is just the door.

### Client Check-in
- Peer-to-peer, no formality
- Specific to their project/situation
- Clear ask or update

---

## Step 1 — Identify the email type and context

Determine:
- Who is the recipient and what's their relationship to Zac?
- What's the purpose? (outreach / follow-up / breakup / proposal / check-in)
- What's the relevant context? (previous convo, mutual connection, their situation)
- Is there an existing Gmail thread to reply into?

---

## Step 2 — Write the draft

Apply the voice rules above. Keep it tight. Read it back — if any line doesn't add value, cut it.

**Subject line rules:**
- Outreach to friends: casual and specific ("random one but might be relevant", "had a thought about X")
- Business follow-up: match the existing thread subject with "Re:" prefix
- New business email: clear but not clickbait ("Elite Systems — follow up from our call")

---

## Step 3 — Create the Gmail draft via MCP

```
gmail_create_draft(
  to="recipient@domain.com",
  subject="Subject line",
  body="Email body",
  cc="cc@domain.com"  # only if needed
)
```

Get recipient email from:
- Context Zac has provided
- Gmail search: `gmail_search_messages(q="from:name OR to:name")`
- Previous thread headers

---

## Step 4 — Confirm

After creating the draft, report back:
- Who it's to
- Subject line
- 1-line summary of what was said
- Confirm it's sitting in Gmail Drafts ready to review and send

---

## Rules

- **Always create a Gmail draft** — never just output the email text
- **Never add length** — if you're unsure whether to include a line, cut it
- **Match the relationship temperature** — a friend gets texting energy, a cold lead gets a slightly more structured approach
- **Check Gmail for context** before writing follow-ups — use `gmail_search_messages` to read the thread
- **Use existing thread subject** for replies so it threads correctly in Gmail
- **CC Alex Gill** (`bd@elitesystems.ai`) on formal proposal emails only — not casual outreach
