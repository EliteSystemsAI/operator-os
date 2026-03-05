#!/usr/bin/env bash
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}OperatorOS Setup${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Check Claude Code
if ! command -v claude &>/dev/null; then
  echo -e "${YELLOW}Claude Code not found.${RESET}"
  echo "Install it from: https://claude.ai/download"
  echo "Then re-run this script."
  exit 1
fi
echo -e "${GREEN}✓${RESET} Claude Code found"

# 2. Python venv
if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi
echo -e "${GREEN}✓${RESET} Python venv ready"

# 3. Install dependencies
echo "Installing Python dependencies..."
.venv/bin/pip install -q -r requirements.txt
echo -e "${GREEN}✓${RESET} Dependencies installed"

# 4. .env setup
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo -e "${YELLOW}Created .env from template.${RESET}"
  echo "Fill in your API keys before running the bot:"
  echo ""
  echo "  Required for Telegram bot: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
  echo "  Required for AI: OPENAI_API_KEY or CLAUDE_CODE_OAUTH_TOKEN"
  echo "  Add others as you enable integrations (GHL, Stripe, etc.)"
  echo ""
  if command -v code &>/dev/null; then
    read -p "Open .env in VS Code? [y/N] " open_env
    [[ "$open_env" =~ ^[Yy]$ ]] && code .env
  else
    echo "Open .env in your editor and fill in your keys."
  fi
else
  echo -e "${GREEN}✓${RESET} .env already exists"
fi

# 5. MCP config
if [ ! -f ".mcp.json" ] && [ -f ".mcp.json.example" ]; then
  cp .mcp.json.example .mcp.json
  echo -e "${GREEN}✓${RESET} .mcp.json created from template"
  echo "   Edit .mcp.json to add your MCP API tokens"
fi

# 6. Upstream remote for future updates
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  if git remote get-url upstream &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${RESET} Upstream remote already configured"
  else
    git remote add upstream https://github.com/EliteSystemsAI/operator-os.git
    echo -e "${GREEN}✓${RESET} Upstream remote configured (run scripts/update.sh to get future improvements)"
  fi
fi

echo ""
echo -e "${BOLD}Setup complete.${RESET}"
echo ""
echo "Next steps:"
echo "  1. Fill in .env with your API keys"
echo "  2. Edit CLAUDE.md — replace all [YOUR_X] placeholders with your business context"
echo "  3. Fill in knowledge/ files with your brand, ICA, and content pillars"
echo "  4. Run: claude"
echo ""
echo "Docs: https://github.com/EliteSystemsAI/operator-os"
echo ""
