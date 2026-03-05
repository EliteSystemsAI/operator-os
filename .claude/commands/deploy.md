# /deploy — Deploy OperatorOS to Mac Mini

Rsyncs the current OperatorOS repo to the Mac Mini and restarts the bot.

## Steps

1. Run the deploy script from the project root:

```bash
cd /Users/ZacsMacBook/Documents/OperatorOS
bash scripts/deploy.sh
```

2. Report the result to Zac:
   - If exit code 0: "Deployed and bot restarted on Mac Mini."
   - If exit code non-zero: show the error output and suggest checking Tailscale connectivity (`ping YOUR_SERVER_IP`) or SSH access (`ssh YOUR_SERVER_USER@YOUR_SERVER_IP

## Notes
- Never sync `.env` — Mac Mini has its own with different credentials
- Safe to run multiple times (idempotent)
- Use `bash scripts/deploy.sh --dry-run` to preview what would be synced without deploying
