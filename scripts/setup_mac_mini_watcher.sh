#!/bin/bash
# Install a launchd watcher on Mac Mini that restarts the bot when a deploy trigger file appears
# Usage: ./scripts/setup_mac_mini_watcher.sh
#
# After installation, trigger a bot restart from MacBook with:
#   ssh YOUR_SERVER_USER@YOUR_SERVER_IP "touch /Users/YOUR_SERVER_USER/operatoros/.deploy-trigger"

set -euo pipefail

MAC_MINI="YOUR_SERVER_USER@YOUR_SERVER_IP
REMOTE_PATH="/Users/YOUR_SERVER_USER/operatoros"
TRIGGER_FILE="$REMOTE_PATH/.deploy-trigger"
WATCHER_SCRIPT="$REMOTE_PATH/scripts/restart_on_trigger.sh"
PLIST_LABEL="com.elitesystems.deploy-watcher"
PLIST_PATH="/Users/YOUR_SERVER_USER/Library/LaunchAgents/$PLIST_LABEL.plist"

echo "Installing deploy watcher on Mac Mini..."

# 1. Write the watcher script to Mac Mini
ssh "$MAC_MINI" "cat > $WATCHER_SCRIPT" << 'SCRIPT'
#!/bin/bash
TRIGGER_FILE="/Users/YOUR_SERVER_USER/operatoros/.deploy-trigger"
LOG_FILE="/Users/YOUR_SERVER_USER/.pm2/logs/deploy-watcher.log"

if [ -f "$TRIGGER_FILE" ]; then
  echo "[$(date)] Deploy trigger detected — restarting your-command-bot" >> "$LOG_FILE"
  rm -f "$TRIGGER_FILE"
  PATH=/opt/homebrew/bin:$PATH pm2 restart your-command-bot --update-env >> "$LOG_FILE" 2>&1
  echo "[$(date)] Restart complete" >> "$LOG_FILE"
fi
SCRIPT

ssh "$MAC_MINI" "chmod +x $WATCHER_SCRIPT"
echo "Watcher script installed at $WATCHER_SCRIPT"

# 2. Write the launchd plist to Mac Mini
# WatchPaths fires when the trigger file is created or modified (kernel-level FSEvents — no polling)
ssh "$MAC_MINI" "cat > $PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$WATCHER_SCRIPT</string>
  </array>
  <key>WatchPaths</key>
  <array>
    <string>$TRIGGER_FILE</string>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/Users/YOUR_SERVER_USER/.pm2/logs/deploy-watcher.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/YOUR_SERVER_USER/.pm2/logs/deploy-watcher-err.log</string>
</dict>
</plist>
PLIST

echo "launchd plist installed at $PLIST_PATH"

# 3. Load (or reload) the launchd service
ssh "$MAC_MINI" "launchctl unload $PLIST_PATH 2>/dev/null || true; launchctl load $PLIST_PATH"
echo "launchd service loaded: $PLIST_LABEL"

echo ""
echo "Setup complete. To trigger a bot restart from MacBook, run:"
echo "  ssh $MAC_MINI 'touch $TRIGGER_FILE'"
echo ""
echo "Logs: ssh $MAC_MINI 'tail -f /Users/YOUR_SERVER_USER/.pm2/logs/deploy-watcher.log'"
