# Team Setup Guide

Internal guide for Elite Systems AI team members getting access to OperatorOS.

## Prerequisites

- Claude Code installed — download at https://claude.ai/download
- SSH key added to GitHub (ask Zac to add yours to the repo)
- Python 3.11+ installed (`python3 --version`)

## Setup (5 minutes)

**1. Clone the repo**
```
git clone git@github.com:elitesystemsai/operatoros.git
cd operatoros
```

**2. Run the setup script**
```
./install.sh
```

This creates your Python venv, installs dependencies, and sets up your `.env` file.

**3. Get credentials from Zac**

Zac will send you a `.env` file with the shared API keys. Replace the `.env` that `install.sh` created with the one he sends. Do not commit this file — it is gitignored.

**4. Open Claude Code**
```
claude
```

You now have the full OperatorOS setup: all commands, all skills, and the same knowledge base and brand voice as Zac.

## What you have access to

- All `/commands` — see CLAUDE.md for the full list
- All skills — content, email, Slack, Drive, leads, invoices, etc.
- Telegram bot access (if your `.env` includes the bot token)
- Full business knowledge base — ICA, brand voice, content pillars

## Important rules

- **Never commit `.env`** — it contains API keys and is gitignored
- **Never push directly to `main`** — use feature branches and open a PR
- **Memory files are local** — `memory/` is gitignored, your session memory stays on your machine
- **Data files are shared** — `data/` is tracked in git, changes sync to everyone

## Getting updates

When Zac ships improvements to OperatorOS, pull them:

```
git pull origin main
```

Your `.env` and `memory/` files are local and will not be affected.

## Troubleshooting

**Claude Code not found**
Download from https://claude.ai/download and run the installer.

**Python venv errors**
Make sure Python 3.11+ is installed: `python3 --version`
If not, install via homebrew: `brew install python@3.11`

**Missing API keys**
Ask Zac for the team `.env` file.

**Bot not responding**
Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set correctly in `.env`.
