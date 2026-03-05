#!/usr/bin/env python3
"""
Elite Systems AI — Claude Code Worker

Runs on Mac Mini (YOUR_SERVER_USER@YOUR_SERVER_IP via pm2.
Polls Supabase work_queue every 30s for 'ready' tasks.
Runs ~/.local/bin/claude --print for each task.
Saves result back to Supabase + sends Telegram summary.

Usage:
  pm2 start ecosystem.config.js --only elite-worker
  OR standalone: python ops/claude_worker.py
"""

import os
import subprocess
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def load_env():
    import os
    env = dict(os.environ)
    for candidate in [Path(__file__).parent.parent / ".env", Path.home() / ".env"]:
        if candidate.exists():
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            break
    return env


env = load_env()

SUPABASE_URL = env.get("SUPABASE_URL", "")
SUPABASE_KEY = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")

CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"
WORK_DIR = Path(__file__).parent.parent
WORKER_CTX = Path.home() / "elite-worker-ctx"  # outside project tree — Claude only loads this CLAUDE.md, not the project's
POLL_INTERVAL = 30  # seconds
TASK_TIMEOUT = 600  # 10 minutes max per task
DASHBOARD_URL = "https://internal.elitesystems.ai/operations"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def fetch_next_task() -> dict | None:
    """Fetch highest-priority ready task, or None."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/work_queue",
        headers=SUPABASE_HEADERS,
        params={
            "status": "eq.ready",
            "order": "priority.asc,created_at.asc",
            "limit": "1",
        },
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def update_task(task_id: str, patch: dict) -> None:
    """PATCH a task row in Supabase."""
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/work_queue",
        headers=SUPABASE_HEADERS,
        params={"id": f"eq.{task_id}"},
        json=patch,
        timeout=10,
    )
    r.raise_for_status()


def send_telegram(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def run_claude(title: str, description: str) -> tuple[str, bool]:
    """
    Run claude --print with the task prompt.
    Returns (output, success).
    """
    prompt = f"{title}\n\n{description}" if description else title

    try:
        # Build a clean environment for the claude subprocess.
        # Strip ALL pm2 vars — pm2 injects NODE_CHANNEL_FD, PM2_HOME, PM2_JSON_PROCESSING,
        # axm_* metrics, and internal state vars. Claude (Node.js) may detect PM2_HOME
        # and attempt to register with the pm2 daemon, hanging when the socket is closed.
        PM2_STRIP_PREFIXES = ("PM2_", "pm_", "axm_", "NODE_")
        PM2_STRIP_EXACT = {
            "unique_id", "status", "pm_id", "namespace", "kill_retry_time",
            "windowsHide", "treekill", "automation", "pmx", "instance_var",
            "max_restarts", "watch", "autorestart", "autostart", "vizion",
            "merge_logs", "restart_delay", "exec_interpreter", "exec_mode",
            "instances", "km_link", "vizion_running", "unstable_restarts",
            "prev_restart_delay", "filter_env", "__PYVENV_LAUNCHER__",
        }
        proc_env = {
            k: v for k, v in env.items()
            if not any(k.startswith(p) for p in PM2_STRIP_PREFIXES)
            and k not in PM2_STRIP_EXACT
        }

        log.info(f"Spawning claude (env keys: {len(proc_env)}, cwd: {WORKER_CTX})")
        result = subprocess.run(
            [str(CLAUDE_BIN), "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(WORKER_CTX),
            env=proc_env,
        )
        log.info(f"Claude exited rc={result.returncode}, stdout={len(result.stdout)}b, stderr={len(result.stderr)}b")
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        success = result.returncode == 0
        return output, success
    except subprocess.TimeoutExpired:
        return f"Task timed out after {TASK_TIMEOUT // 60} minutes.", False
    except Exception as e:
        return f"Worker error: {e}", False


def process_task(task: dict) -> None:
    task_id = task["id"]
    title = task["title"]
    description = task.get("description") or ""
    priority = task.get("priority", 3)

    log.info(f"[{task_id[:8]}] Starting: {title}")

    # Mark in_progress
    update_task(task_id, {
        "status": "in_progress",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    # Notify Telegram for high-priority tasks
    if priority <= 2:
        send_telegram(
            f"⚙️ *Working on:* {title}\n"
            f"_Priority: {'🔴 Critical' if priority == 1 else '🟠 High'}_"
        )

    # Run Claude
    output, success = run_claude(title, description)

    # Split result
    result_summary = output[:400] + ("..." if len(output) > 400 else "")
    result_full = output

    # Save result
    status = "done" if success else "failed"
    update_task(task_id, {
        "status": status,
        "result_summary": result_summary,
        "result_full": result_full,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    # Send Telegram summary
    icon = "✅" if success else "❌"
    msg = (
        f"{icon} *{title}*\n\n"
        f"{result_summary}\n\n"
        f"[Full output →]({DASHBOARD_URL}?task={task_id})"
    )
    send_telegram(msg)
    log.info(f"[{task_id[:8]}] {status}: {title}")


def main():
    log.info(f"Elite Worker starting. Claude: {CLAUDE_BIN}, Work dir: {WORK_DIR}")

    if not CLAUDE_BIN.exists():
        log.error(f"Claude binary not found at {CLAUDE_BIN}")
        sys.exit(1)

    log.info(f"Polling Supabase every {POLL_INTERVAL}s for ready tasks...")

    while True:
        try:
            task = fetch_next_task()
            if task:
                process_task(task)
            else:
                log.debug("No ready tasks, sleeping...")
        except KeyboardInterrupt:
            log.info("Worker stopped.")
            break
        except Exception as e:
            log.exception(f"Worker loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
