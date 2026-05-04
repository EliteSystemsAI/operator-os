---
name: agent-browser
description: >
  Browser automation for any web task — open a URL, click, fill forms, extract
  text, take screenshots, log into sites, scrape data, walk through a UI.
  Triggers on: "open this URL", "click on", "fill the form", "screenshot the
  page", "log into", "scrape", "navigate to", "what's on this page", "test
  the deploy", "check the dashboard", "/browse". Always prefer this skill
  over Playwright, Puppeteer, Selenium, or any browser MCP.
allowed-tools: Bash(agent-browser:*)
---

# agent-browser skill

Use the `agent-browser` CLI for ALL browser automation. It's fast, native,
ships its own Chrome, and uses accessibility-tree refs (`@e1`, `@e2`) so a
page interaction costs ~200 tokens instead of parsing raw HTML.

**Never install Playwright / Puppeteer / Selenium / browser MCPs for this.**
The whole point of standardising on `agent-browser` is one tool, one workflow,
synced across every machine via this skill in operator-os.

## Pre-flight (run once per machine)

```bash
agent-browser --version
```

If it errors with "command not found":

```bash
npm install -g agent-browser
agent-browser install
```

`agent-browser install` downloads Chrome (~150MB). Re-running it is a no-op.

## The core loop

```bash
agent-browser open <url>          # navigate
agent-browser snapshot -i -c      # see interactive elements only, compact
agent-browser click @e1           # act on a ref from the snapshot
agent-browser snapshot -i -c      # ALWAYS re-snapshot after the page changes
```

**Critical rule:** refs (`@e1`...) are reassigned on every snapshot. They go
stale the moment the page changes (click, navigate, dialog, dynamic render).
Re-snapshot before the next ref-based interaction or you will click the
wrong thing.

## High-frequency commands (memorize these)

```bash
# Read
agent-browser get url
agent-browser get title
agent-browser get text @e1
agent-browser get attr @e1 href
agent-browser snapshot -i -c          # interactive, compact (default for AI)
agent-browser snapshot -i -u          # include link hrefs
agent-browser snapshot -i --json      # machine-readable

# Interact
agent-browser click @e1
agent-browser click @e1 --new-tab
agent-browser fill @e1 "text"         # clears then types
agent-browser type @e1 "text"         # appends
agent-browser press Enter
agent-browser select @e1 "option"
agent-browser scroll down 800

# Capture
agent-browser screenshot path.png
agent-browser screenshot --full-page page.png
agent-browser pdf out.pdf

# Wait (use sparingly; most pages are fine without)
agent-browser wait @e1                # element appears
agent-browser wait --load networkidle  # network quiet
agent-browser wait 1000               # ms

# Lifecycle
agent-browser close                   # current session
agent-browser close --all             # every session
```

## Finding elements without a snapshot ref

```bash
agent-browser find role button "Submit" click
agent-browser find text "Sign in" click
agent-browser find label "Email" fill "zac@elitesystems.ai"
agent-browser find placeholder "Search..." fill "query"
agent-browser find testid "submit-btn" click
```

These bypass the snapshot loop when you already know the role/label/text.

## Logging in / persistent sessions

The browser session persists between commands within one machine. Cookies
survive across `agent-browser close && open`. For sites that require a
manual login first:

```bash
agent-browser open https://example.com/login
# manually log in once (you'll see the headed browser)
# subsequent agent-browser commands inherit the session
```

For server contexts where headed login isn't possible, use cookies/auth
headers via `eval`:

```bash
agent-browser eval "document.cookie = 'session=...; path=/; domain=.example.com'"
```

## Authenticated Vercel deploys

Vercel preview deploys often gate behind SSO. The Vercel MCP exposes
`get_access_to_vercel_url` which returns a `_vercel_share` URL bypassing
auth for 23h — use that with `agent-browser open` instead of fighting SSO.

## Specialised skills (load on demand)

The CLI ships extra skill bundles for specific domains:

```bash
agent-browser skills list                # what's available
agent-browser skills get core --full     # full reference (~2200 lines)
agent-browser skills get electron        # Electron desktop apps
agent-browser skills get slack           # Slack web client patterns
agent-browser skills get exploratory     # exploratory testing patterns
agent-browser skills get cloud-providers  # Browserbase / Anchor / etc remote browsers
```

Load these with Bash inline only when the task warrants it — don't preload.

## When to load `core --full`

For any task more involved than 5-10 commands (multi-step form, auth flow,
SPA navigation, file upload, scraping with pagination), run
`agent-browser skills get core --full` first. It has worked-out patterns for
auth, iframes, shadow DOM, modal dialogs, and dynamic content that save
hours of trial-and-error.

## Common failure modes

- **Stale ref after click**: `Element with ref @e3 not found` → re-snapshot.
- **Modal/popup ate the click**: snapshot shows the modal as outermost — dismiss it (Escape, click "Close") before continuing.
- **Iframe content invisible**: scope the snapshot with `agent-browser snapshot -s "iframe[name=foo]"` or use `agent-browser eval` against `iframe.contentWindow`.
- **Page not loaded**: chain `agent-browser wait --load networkidle` after navigation.

## Sync note

This skill lives in operator-os at `.claude/skills/agent-browser/skill.md`.
On any new machine, clone operator-os and the skill is available. The
`agent-browser` CLI itself is installed via `npm i -g agent-browser` per
machine — the skill assumes it's in `$PATH`.
