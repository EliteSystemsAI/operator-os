#!/bin/bash
# Telegram bot now runs on Mac Mini via PM2 (your-command-bot).
# Railway only runs the FastAPI web server.
echo "Starting FastAPI web server..."
uvicorn ops.slack_listener:app --host 0.0.0.0 --port "${PORT:-8000}"
