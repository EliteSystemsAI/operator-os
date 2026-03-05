#!/usr/bin/env bash
set -e

PRIVATE_REPO="/Users/ZacsMacBook/Documents/OperatorOS"
TEMPLATE_REPO="${1:-$HOME/Documents/operator-os}"
TEMPLATE_REMOTE="git@github.com:EliteSystemsAI/operator-os.git"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}Exporting OperatorOS template...${RESET}"
echo "  Source: $PRIVATE_REPO"
echo "  Target: $TEMPLATE_REPO"
echo ""

# Clone template repo if it doesn't exist locally
if [ ! -d "$TEMPLATE_REPO/.git" ]; then
  echo "Cloning template repo to $TEMPLATE_REPO..."
  git clone "$TEMPLATE_REMOTE" "$TEMPLATE_REPO"
  echo ""
fi

# Remove any private-only dirs/files that may exist from a previous export
# (rsync --delete won't remove excluded items, so we clean them manually)
echo "Cleaning previous private files from template..."
rm -rf \
  "$TEMPLATE_REPO/docs/plans" \
  "$TEMPLATE_REPO/tasks" \
  "$TEMPLATE_REPO/memory" \
  "$TEMPLATE_REPO/content" \
  "$TEMPLATE_REPO/output" \
  "$TEMPLATE_REPO/TASK.md" \
  "$TEMPLATE_REPO/.claude/compact-reminder.md" \
  "$TEMPLATE_REPO/knowledge/personal_anecdotes.md" \
  "$TEMPLATE_REPO/knowledge/content_strategy.md" \
  "$TEMPLATE_REPO/knowledge/META_ADS_PLAYBOOK.md" \
  "$TEMPLATE_REPO/knowledge/DM_QUALIFICATION_SCRIPT.md" \
  "$TEMPLATE_REPO/knowledge/GHL_DM_WORKFLOW.md" \
  "$TEMPLATE_REPO/knowledge/GHL_INTEGRATION.md" \
  "$TEMPLATE_REPO/knowledge/META_INSTANT_REPLY.md" \
  "$TEMPLATE_REPO/knowledge/winning_patterns.md" \
  "$TEMPLATE_REPO/knowledge/COMPETITORS.md" \
  "$TEMPLATE_REPO/knowledge/DEPLOYMENT_SETUP.md" \
  "$TEMPLATE_REPO/knowledge/client_delivery_template.md" \
  2>/dev/null || true
echo -e "  ${GREEN}✓${RESET} Cleaned"

# Rsync structural files (exclude all personal/private content)
echo "Syncing files..."
rsync -a --delete \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.mcp.json' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='data/' \
  --exclude='tasks/' \
  --exclude='memory/' \
  --exclude='content/' \
  --exclude='output/' \
  --exclude='.playwright-mcp/' \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='.drive_root_id' \
  --exclude='worker_context/' \
  --exclude='mac-mini-config/' \
  --exclude='TASK.md' \
  --exclude='.claude/compact-reminder.md' \
  --exclude='CLAUDE.template.md' \
  --exclude='knowledge/*.template.md' \
  --exclude='docs/plans/' \
  --exclude='knowledge/personal_anecdotes.md' \
  --exclude='knowledge/content_strategy.md' \
  --exclude='knowledge/META_ADS_PLAYBOOK.md' \
  --exclude='knowledge/DM_QUALIFICATION_SCRIPT.md' \
  --exclude='knowledge/GHL_DM_WORKFLOW.md' \
  --exclude='knowledge/GHL_INTEGRATION.md' \
  --exclude='knowledge/META_INSTANT_REPLY.md' \
  --exclude='knowledge/winning_patterns.md' \
  --exclude='knowledge/COMPETITORS.md' \
  --exclude='knowledge/DEPLOYMENT_SETUP.md' \
  --exclude='knowledge/client_delivery_template.md' \
  "$PRIVATE_REPO/" "$TEMPLATE_REPO/"

# Sanitize hardcoded personal values in exported files
echo "Sanitizing personal references..."
find "$TEMPLATE_REPO" -not -path '*/.git/*' \( -name '*.md' -o -name '*.py' -o -name '*.sh' -o -name '*.json' -o -name '*.txt' \) | while read -r file; do
  sed -i '' \
    -e 's/YOUR_SERVER_USER@YOUR_SERVER_IP ]*/YOUR_SERVER_USER@YOUR_SERVER_IP/g' \
    -e 's/100\.64\.172\.78/YOUR_SERVER_IP/g' \
    -e 's/[YOUR_INSTAGRAM_HANDLE]/[YOUR_INSTAGRAM_HANDLE]/g' \
    -e 's/[YOUR_NAME]/[YOUR_NAME]/g' \
    -e 's/YOUR_SERVER_USER/YOUR_SERVER_USER/g' \
    -e 's/your-command-bot/your-command-bot/g' \
    "$file" 2>/dev/null || true
done
echo -e "  ${GREEN}✓${RESET} Personal references sanitized"

# Replace CLAUDE.md with the sanitized template version
if [ -f "$PRIVATE_REPO/CLAUDE.template.md" ]; then
  cp "$PRIVATE_REPO/CLAUDE.template.md" "$TEMPLATE_REPO/CLAUDE.md"
  echo -e "  ${GREEN}✓${RESET} Replaced CLAUDE.md with template version"
else
  echo -e "  ${YELLOW}Warning: CLAUDE.template.md not found — CLAUDE.md not replaced${RESET}"
fi

# Replace knowledge files with template versions
for template_file in "$PRIVATE_REPO"/knowledge/*.template.md; do
  [ -f "$template_file" ] || continue
  base=$(basename "$template_file" .template.md)
  cp "$template_file" "$TEMPLATE_REPO/knowledge/${base}.md"
  echo -e "  ${GREEN}✓${RESET} Replaced knowledge/${base}.md with template version"
done

# Safety check: scan for personal content that shouldn't be in template
# (exclude this script itself — it contains the search terms as grep patterns)
echo ""
echo "Running safety check..."
LEAKS=0
EXPORT_SCRIPT="$TEMPLATE_REPO/scripts/export-template.sh"
for term in "[YOUR_NAME]" "[YOUR_INSTAGRAM_HANDLE]" "YOUR_SERVER_USER" "YOUR_SERVER_IP" "sk-ant-oat01" "sk_live_"; do
  if grep -r --include="*.md" --include="*.py" --include="*.sh" --include="*.json" -l "$term" "$TEMPLATE_REPO" 2>/dev/null \
    | grep -v '.git' \
    | grep -v "$EXPORT_SCRIPT" \
    | grep -q .; then
    FILES=$(grep -r --include="*.md" --include="*.py" --include="*.sh" --include="*.json" -l "$term" "$TEMPLATE_REPO" 2>/dev/null | grep -v '.git' | grep -v "$EXPORT_SCRIPT")
    echo -e "  ${YELLOW}Warning: found '$term' in:${RESET}"
    echo "$FILES" | sed 's|'"$TEMPLATE_REPO"'/||' | sed 's/^/    /'
    LEAKS=$((LEAKS + 1))
  fi
done
if [ $LEAKS -eq 0 ]; then
  echo -e "  ${GREEN}✓${RESET} No personal content detected"
else
  echo -e "  ${YELLOW}$LEAKS leak(s) found — review before pushing${RESET}"
  read -p "Continue anyway? [y/N] " confirm
  [[ ! "$confirm" =~ ^[Yy]$ ]] && echo "Aborted." && exit 1
fi

# Commit and push
cd "$TEMPLATE_REPO"
DATE=$(date +%Y-%m-%d)
git add -A

if git diff --cached --quiet; then
  echo ""
  echo "No changes to export — template is already up to date."
  exit 0
fi

git commit -m "chore: export from OperatorOS private repo ($DATE)"
git push origin main
echo ""
echo -e "${GREEN}Exported and pushed to $TEMPLATE_REMOTE${RESET}"

# Tag the release (only one tag per date)
TAG="v$DATE"
if ! git tag | grep -q "^${TAG}$"; then
  git tag "$TAG"
  git push origin "$TAG"
  echo "Tagged release: $TAG"
fi

echo ""
echo -e "${BOLD}Done.${RESET} Public template updated."
echo "View at: https://github.com/EliteSystemsAI/operator-os"
echo ""
