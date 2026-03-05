#!/bin/bash
# Pull memory, lessons, and data back from Mac Mini to MacBook
# Usage: ./scripts/sync_from_mini.sh [--dry-run]
#
# Syncs:
#   memory/                          <- business state, lessons
#   data/revenue_history.json        <- revenue records
#   data/client_health_snapshot.json <- client health data
#   data/ig_today.json               <- IG post data for today
#   tasks/lessons.md                 <- self-improvement log

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

RSYNC_FLAGS="-avz"
if $DRY_RUN; then
  RSYNC_FLAGS="-avzn"
  echo "[dry-run] Showing what would be pulled from $MAC_MINI"
fi

echo "Pulling memory/ from Mac Mini..."
rsync $RSYNC_FLAGS \
  "$MAC_MINI:$REMOTE_PATH/memory/" \
  "$LOCAL_PATH/memory/"

echo "Pulling tasks/lessons.md from Mac Mini..."
rsync $RSYNC_FLAGS \
  "$MAC_MINI:$REMOTE_PATH/tasks/lessons.md" \
  "$LOCAL_PATH/tasks/lessons.md"

echo "Pulling data files from Mac Mini..."
for file in revenue_history.json client_health_snapshot.json ig_today.json; do
  rsync $RSYNC_FLAGS \
    "$MAC_MINI:$REMOTE_PATH/data/$file" \
    "$LOCAL_PATH/data/$file" 2>/dev/null || echo "  skipped $file (not found on Mac Mini)"
done

if $DRY_RUN; then
  echo "[dry-run] No files transferred."
else
  echo "Sync from Mac Mini complete."
fi
