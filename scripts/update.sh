#!/usr/bin/env bash
set -e

TEMPLATE_REMOTE="https://github.com/EliteSystemsAI/operator-os.git"
UPSTREAM_BRANCH="main"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RESET="\033[0m"

# Must be run from inside the repo
if ! git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  echo "Error: not inside a git repository. Run this from your operatoros directory."
  exit 1
fi

# Set up upstream remote if not already there
if ! git remote get-url upstream &>/dev/null 2>&1; then
  git remote add upstream "$TEMPLATE_REMOTE"
  echo "Added upstream remote: $TEMPLATE_REMOTE"
fi

echo "Fetching updates from upstream..."
git fetch upstream --quiet

# Check if there are new commits
BEHIND=$(git rev-list HEAD..upstream/$UPSTREAM_BRANCH --count 2>/dev/null || echo 0)

if [ "$BEHIND" -eq 0 ]; then
  echo -e "${GREEN}Already up to date.${RESET}"
  exit 0
fi

echo ""
echo -e "${BOLD}$BEHIND update(s) available:${RESET}"
git log HEAD..upstream/$UPSTREAM_BRANCH --oneline
echo ""
echo "These files will be updated (your CLAUDE.md, knowledge/, and .env will NOT be touched):"
echo ""

# Structural paths safe to update
SAFE_PATHS=(
  ".claude/commands"
  ".claude/skills"
  ".claude/settings.json"
  "scripts"
  "ops"
  "apps"
  "requirements.txt"
  "install.sh"
  "README.md"
)

# Show preview of what would change
for path in "${SAFE_PATHS[@]}"; do
  if git ls-tree upstream/$UPSTREAM_BRANCH "$path" &>/dev/null 2>&1; then
    echo "  $path"
  fi
done

echo ""
read -p "Apply updates? [y/N] " confirm
[[ ! "$confirm" =~ ^[Yy]$ ]] && echo "Skipped." && exit 0

# Checkout only safe paths from upstream
UPDATED=0
for path in "${SAFE_PATHS[@]}"; do
  if git ls-tree upstream/$UPSTREAM_BRANCH "$path" &>/dev/null 2>&1; then
    git checkout upstream/$UPSTREAM_BRANCH -- "$path" 2>/dev/null && \
      echo -e "  ${GREEN}✓${RESET} Updated: $path" && UPDATED=$((UPDATED + 1)) || true
  fi
done

echo ""
if [ $UPDATED -gt 0 ]; then
  echo -e "${BOLD}Update applied.${RESET} $UPDATED path(s) updated."
  echo "Your personal files are untouched."
  echo ""
  echo "Review changes: git diff HEAD"
  echo "Commit when ready: git add -A && git commit -m \"chore: apply upstream updates\""
else
  echo "Nothing to update."
fi
echo ""
