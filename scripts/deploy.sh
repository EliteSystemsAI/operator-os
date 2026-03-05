#!/bin/bash
# Deploy OperatorOS to Mac Mini and restart the bot
# Usage: ./scripts/deploy.sh [--dry-run]
#
# --dry-run: show what would be synced without transferring files or restarting

set -euo pipefail

MAC_MINI="YOUR_SERVER_USER@YOUR_SERVER_IP
REMOTE_PATH="/Users/YOUR_SERVER_USER/operatoros"
LOCAL_PATH="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
  esac
done

if $DRY_RUN; then
  echo "[dry-run] Showing what would be synced to $MAC_MINI:$REMOTE_PATH"
  rsync -avzn \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='data/' \
    --exclude='.env' \
    --exclude='output/' \
    "$LOCAL_PATH/" \
    "$MAC_MINI:$REMOTE_PATH/"
  echo "[dry-run] Bot restart skipped."
  exit 0
fi

echo "Syncing to Mac Mini..."
rsync -avz \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='data/' \
  --exclude='.env' \
  --exclude='output/' \
  "$LOCAL_PATH/" \
  "$MAC_MINI:$REMOTE_PATH/"

echo "Restarting bot on Mac Mini..."
ssh "$MAC_MINI" 'PATH=/opt/homebrew/bin:$PATH pm2 restart your-command-bot --update-env'

echo "Deployed and restarted."
