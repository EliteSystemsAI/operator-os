#!/usr/bin/env python3
"""
ClickUp API helper for OperatorOS.

Token read from CLICKUP_API_TOKEN env var.
Base URL: https://api.clickup.com/api/v2

All functions fail gracefully — log warning and return None/False on any error.
"""

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_BASE_URL = "https://api.clickup.com/api/v2"

# Hardcoded workspace/list IDs
WORKSPACE_ID = "9016608196"
LIST_PROJECTS = "901609565565"        # Agency PM > Projects
LIST_CLIENT_SUCCESS = "901608631275"  # Client Success Tracker


def _token() -> str:
    return os.getenv("CLICKUP_API_TOKEN", "")


def _headers() -> dict:
    return {
        "Authorization": _token(),
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, **kwargs) -> requests.Response | None:
    """Make a ClickUp API request with one 429 retry."""
    if not _token():
        log.warning("clickup: CLICKUP_API_TOKEN not set")
        return None

    url = f"{_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=10, **kwargs)
        if resp.status_code == 429:
            log.warning("clickup: rate limited — retrying after 1s")
            time.sleep(1)
            resp = requests.request(method, url, headers=_headers(), timeout=10, **kwargs)
        return resp
    except Exception as e:
        log.warning("clickup: request error %s %s — %s", method, path, e)
        return None


def create_task(
    list_id: str,
    title: str,
    description: str = "",
    status: str = "to do",
    tags: list[str] | None = None,
) -> str | None:
    """Create a task in the given list. Returns task_id or None on failure."""
    body: dict = {"name": title, "description": description}
    if status and status not in ("to do", "open", ""):
        body["status"] = status
    if tags:
        body["tags"] = tags

    resp = _request("POST", f"/list/{list_id}/task", json=body)
    if resp is None:
        return None
    if not resp.ok:
        log.warning("clickup.create_task failed: %s %s", resp.status_code, resp.text[:200])
        return None

    try:
        return resp.json().get("id")
    except Exception as e:
        log.warning("clickup.create_task parse error: %s", e)
        return None


def find_task_by_name(list_id: str, name: str) -> dict | None:
    """Search tasks by name. Returns first match or None."""
    resp = _request("GET", f"/list/{list_id}/task", params={"search": name})
    if resp is None:
        return None
    if not resp.ok:
        log.warning("clickup.find_task_by_name failed: %s %s", resp.status_code, resp.text[:200])
        return None

    try:
        tasks = resp.json().get("tasks", [])
        return tasks[0] if tasks else None
    except Exception as e:
        log.warning("clickup.find_task_by_name parse error: %s", e)
        return None


def add_comment(task_id: str, comment: str) -> bool:
    """Add a comment to a task. Returns True on success."""
    resp = _request("POST", f"/task/{task_id}/comment", json={"comment_text": comment})
    if resp is None:
        return False
    if not resp.ok:
        log.warning("clickup.add_comment failed: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


def update_task_status(task_id: str, status: str) -> bool:
    """Update the status of a task. Returns True on success."""
    resp = _request("PUT", f"/task/{task_id}", json={"status": status})
    if resp is None:
        return False
    if not resp.ok:
        log.warning("clickup.update_task_status failed: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


def log_work_session(
    title: str,
    description: str,
    tags: list[str] | None = None,
) -> str | None:
    """Create a task in LIST_PROJECTS to auto-log a CC session. Returns task_id or None."""
    return create_task(
        list_id=LIST_PROJECTS,
        title=title,
        description=description,
        tags=tags,
    )
