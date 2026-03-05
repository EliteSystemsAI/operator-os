"""Configuration for AI Command Bot."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    bot_token: str
    group_id: int
    anthropic_api_key: str
    openai_api_key: str
    workspace_dir: str
    log_dir: Path
    general_agent_model: str
    general_agent_max_turns: int
    general_agent_max_budget: float
    context_warning_threshold: int
    self_anneal_thread_id: int | None

    # Optional Telegram forum topic IDs for routing scheduled messages.
    # If None, messages go to the group root (or General topic).
    # Set TELEGRAM_TOPIC_GENERAL, TELEGRAM_TOPIC_CONTENT, TELEGRAM_TOPIC_CLIENTS in .env.
    topic_general: int | None = None   # morning ping, startup, bottleneck hunter
    topic_content: int | None = None   # content digest
    topic_clients: int | None = None   # client health


def load_config() -> Config:
    """Load configuration from .env file.

    Workspace directory is auto-detected from this file's location:
    apps/command/config.py -> ../../ = workspace root.
    """
    workspace_dir = Path(__file__).resolve().parent.parent.parent
    env_path = workspace_dir / ".env"
    load_dotenv(env_path)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required in .env")

    group_id_str = os.getenv("TELEGRAM_GROUP_ID", "").strip()
    if not group_id_str:
        raise ValueError("TELEGRAM_GROUP_ID is required in .env")
    group_id = int(group_id_str)

    # The Agent SDK uses Claude Code's built-in auth (~/.claude/), so this key
    # is optional — agents will authenticate via the existing claude CLI session.
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    # Not required — voice note transcription just won't work without it

    log_dir_str = os.getenv("COMMAND_LOG_DIR", "").strip()
    log_dir = Path(log_dir_str) if log_dir_str else workspace_dir / "data" / "command"

    def _topic(env_var: str) -> int | None:
        val = os.getenv(env_var, "").strip()
        return int(val) if val else None

    return Config(
        bot_token=bot_token,
        group_id=group_id,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key or "",
        workspace_dir=str(workspace_dir),
        log_dir=log_dir,
        general_agent_model=os.getenv("COMMAND_GENERAL_MODEL", "sonnet"),
        general_agent_max_turns=int(os.getenv("COMMAND_GENERAL_MAX_TURNS", "30")),
        general_agent_max_budget=float(os.getenv("COMMAND_GENERAL_MAX_BUDGET", "5.00")),
        context_warning_threshold=int(os.getenv("COMMAND_CONTEXT_WARNING_TOKENS", "180000")),
        self_anneal_thread_id=int(os.getenv("SELF_ANNEAL_THREAD_ID")) if os.getenv("SELF_ANNEAL_THREAD_ID") else None,
        topic_general=_topic("TELEGRAM_TOPIC_GENERAL"),
        topic_content=_topic("TELEGRAM_TOPIC_CONTENT"),
        topic_clients=_topic("TELEGRAM_TOPIC_CLIENTS"),
    )
