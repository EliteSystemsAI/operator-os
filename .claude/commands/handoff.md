# /handoff — Session State Capture

Captures current session state so a fresh Claude session can resume instantly.

## When to use
- Context window is getting large (>100k tokens)
- Switching to a different machine or session
- Pausing for the day
- Before a complex task that might consume the whole context

## Steps

### Step 1: Gather state
Run these in parallel to collect current state:

```bash
# Git status across relevant projects
git -C /Users/ZacsMacBook/Documents/OperatorOS status --short
git -C "/Users/ZacsMacBook/Documents/CSA Scheduling" status --short 2>/dev/null

# What branch are we on
git -C /Users/ZacsMacBook/Documents/OperatorOS branch --show-current
git -C "/Users/ZacsMacBook/Documents/CSA Scheduling" branch --show-current 2>/dev/null
```

### Step 2: Read task list
Check TaskList for in-progress and pending tasks.

### Step 3: Read MEMORY.md
Read `/Users/ZacsMacBook/.claude/projects/-Users-ZacsMacBook-Documents-OperatorOS/memory/MEMORY.md` for persistent context.

### Step 4: Output the handoff document

Format it as:

```
# Session Handoff — [DATE TIME AEST]

## What was being worked on
[1-3 sentences describing the active task and where it got to]

## Blocking issues
[List anything that is blocked and WHY — what needs to happen to unblock]

## Files modified this session (not yet committed)
[git status output — or "none"]

## In-progress tasks
[From TaskList — just the in-progress ones]

## Next actions (in order)
1. [Most important thing to do next]
2. [Second thing]
3. [Third thing]

## Key context a fresh session needs
[Any non-obvious context: credentials, URLs, decisions made, etc.]

## Commands to resume
[Exact bash commands to get back to working state — e.g. start local server, SSH tunnel, etc.]
```

### Step 5: Save to file
Save the handoff doc to `/tmp/handoff-[YYYY-MM-DD].md` and display the path.

### Rules
- Be specific — a fresh Claude has zero context
- Include exact file paths, not vague references
- If a task is blocked by "can't find X", say exactly where you looked
- Paste the handoff doc content in-chat AND save to file
