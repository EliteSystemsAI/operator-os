# OperatorOS

Your Claude Code workspace — built for business operators who want AI that actually runs their work.

---

## What is this

OperatorOS is a pre-configured Claude Code workspace. You get a full command library, AI skills, business integrations, and a Telegram bot — all wired together. Clone it, fill in your credentials, open Claude Code. Done.

---

## What you get

- 15+ slash commands covering content creation, revenue reporting, lead management, ad management, scheduling, and ops
- 12 skills for Google Drive, Slack, email inbox triage, lead scraping, invoice extraction, content repurposing, cold email campaigns, thumbnail generation, website building, and more
- Telegram bot for mobile control of your AI system — run commands and get alerts from your phone
- MCP integrations: Supabase (memory and data), Google Drive (file storage), Playwright (browser automation), Context7 (docs)
- One-command deploy to a Mac Mini or VPS so the bot runs 24/7
- Auto-update system — improvements flow to you automatically without touching your config

---

## Quick Start

```bash
git clone https://github.com/elitesystemsai/operatoros-template my-operator-os
cd my-operator-os
./install.sh
```

Then:

1. Fill in `.env` with your API keys
2. Edit `CLAUDE.md` with your business details
3. Fill in your `knowledge/` files
4. Run `claude` in the project directory

---

## Setup Guide

### Fill in CLAUDE.md

Open `CLAUDE.md` and replace the `[YOUR_X]` placeholders:

- Your name and business name
- Your role and positioning headline
- Your social handles
- A one-paragraph description of your ideal customer

This is the brain of the system. The more specific you are, the better every command performs.

### Fill in knowledge files

Three files Claude reads before doing any content or strategy work:

- `knowledge/brand_voice.md` — your tone, rules, phrases to use, phrases to never use
- `knowledge/ica_profile.md` — your customer avatar: who they are, what they fear, what they want
- `knowledge/content_pillars.md` — your content strategy: pillars, topics, posting cadence

Copy the examples already in those files and replace them with your own.

### Configure MCPs

```bash
cp .mcp.json.example .mcp.json
```

Fill in your tokens for the integrations you want to use:

- **Supabase:** get your project URL and service key from [supabase.com/dashboard](https://supabase.com/dashboard)
- **Google Drive:** create OAuth credentials at [console.cloud.google.com](https://console.cloud.google.com), run the auth flow, paste the refresh token

### Set up .env

Required keys to get started:

```
CLAUDE_CODE_OAUTH_TOKEN=    # OR OPENAI_API_KEY — at least one AI key is required
TELEGRAM_BOT_TOKEN=         # required if you want the mobile bot
```

Optional keys (enable additional commands):

```
GHL_API_KEY=                # GoHighLevel — social scheduling + CRM
GHL_LOCATION_ID=
META_ACCESS_TOKEN=          # Meta ads management
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
STRIPE_SECRET_KEY=          # revenue reporting
SLACK_USER_TOKEN=           # Slack messaging
CLICKUP_API_KEY=            # task management
```

### Run Claude Code

```bash
claude
```

Open Claude Code in the project directory. Your commands and skills are immediately available.

---

## Commands Reference

| Command | What it does |
|---|---|
| `/morning` | Daily briefing with trending AI news and top 3 script opportunities |
| `/trending` | Deep trend analysis across 8 AI sub-categories with scores |
| `/script [topic]` | Full reel script in your voice, hook options, and self-critique |
| `/hooks [topic]` | 5 hook A/B variations with angle analysis |
| `/reel` | Analyze latest IG post performance and save to database |
| `/resource-script` | Find a free AI resource and generate a "comment X for this" viral script |
| `/repurpose [url]` | YouTube or video URL to 5 platform-native posts, scheduled via GHL |
| `/ads [subcommand]` | Meta ads: report, create, optimize, copy, audience |
| `/schedule` | View 14-day content calendar and flag gaps |
| `/post` | Create and format a post, add to queue, schedule via GHL |
| `/leads` | GHL pipeline snapshot: qualified leads, stalled deals, actions needed |
| `/revenue` | Stripe revenue snapshot: MTD, MoM trend, run rate |
| `/notify [message]` | Send a Telegram alert to your phone |
| `/carousel personal [topic]` | Personal story carousel, 8 slides, MOFU/BOFU |
| `/carousel quote [topic]` | Quote post layout for a shareable single image |
| `/carousel comparison [topic]` | Comparison post in "Some vs Others" style |
| `/carousel batch` | Generate one of each carousel type for the week |
| `/handoff` | Capture session state for a fresh Claude session to resume |

---

## Integrations

| Integration | Required? |
|---|---|
| Claude Code | Required |
| Python 3.11+ | Required |
| Telegram | Optional — mobile bot control |
| GHL / GoHighLevel | Optional — social scheduling and CRM |
| Meta / Instagram | Optional — ads management and IG analytics |
| Supabase | Optional — persistent memory and data storage |
| Google Drive | Optional — file storage and document creation |
| Stripe | Optional — revenue tracking and reporting |
| Slack | Optional — team messaging |
| ClickUp | Optional — task and project management |

---

## Keeping up to date

```bash
bash scripts/update.sh
```

Pulls new commands, skills, and scripts from upstream. Your `CLAUDE.md`, `knowledge/` files, and `.env` are never touched by the update script.

On each Claude Code session start, you will see a notification if updates are available.

---

## Deploy to a server (optional)

If you want the Telegram bot running 24/7 on a Mac Mini or VPS:

```bash
bash scripts/deploy.sh
```

See `docs/team-setup.md` for full server setup instructions including PM2 configuration, auth token setup, and SSH access.

---

## About

Built by [Elite Systems AI](https://elitesystems.ai).

If you want help setting this up for your business or want a done-for-you version, reach out at [elitesystems.ai](https://elitesystems.ai).
