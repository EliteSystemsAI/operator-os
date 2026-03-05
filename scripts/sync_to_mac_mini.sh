#!/bin/bash
# Sync Elite Operator OS to Mac Mini
# Run from project root: ./scripts/sync_to_mac_mini.sh

MAC_MINI="YOUR_SERVER_USER@YOUR_SERVER_IP
REMOTE_PATH="~/operatoros"
LOCAL_PATH="$(dirname "$(dirname "$0")")"

echo "🔄 Syncing to Mac Mini ($MAC_MINI)..."

rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='output/' --exclude='*.png' \
  --exclude='.env' \
  "$LOCAL_PATH/" \
  "$MAC_MINI:$REMOTE_PATH/"

echo "📋 Syncing .env..."
scp "$LOCAL_PATH/.env" "$MAC_MINI:$REMOTE_PATH/.env"

echo "📋 Syncing worker context (~/elite-worker-ctx)..."
ssh "$MAC_MINI" "mkdir -p ~/elite-worker-ctx"
rsync -avz worker_context/CLAUDE.md "$MAC_MINI:~/elite-worker-ctx/CLAUDE.md"

echo "📋 Syncing Claude Code config to Mac Mini (~/.claude)..."
ssh "$MAC_MINI" "mkdir -p ~/.claude/agents ~/.claude/hooks"
rsync -avz mac-mini-config/.claude/ "$MAC_MINI:~/.claude/"
ssh "$MAC_MINI" "chmod +x ~/.claude/hooks/*.sh"

echo "📋 Syncing Google OAuth token..."
if [ -f "$HOME/.config/elite-os/google-token.json" ]; then
  ssh "$MAC_MINI" "mkdir -p ~/.config/elite-os"
  scp "$HOME/.config/elite-os/google-token.json" "$MAC_MINI:~/.config/elite-os/google-token.json"
  echo "✅ Google token synced"
else
  echo "⚠️  No Google token at ~/.config/elite-os/google-token.json — skipping"
fi

echo "✅ Sync complete!"
