"""Configuration management for vlooper."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Config:  # pylint: disable=too-many-instance-attributes
    """Configuration settings loaded from environment variables."""

    org_name: str = field(
        default_factory=lambda: os.environ.get("ORG_NAME", "ai-warevo")
    )
    bot_username: str = field(
        default_factory=lambda: os.environ.get("BOT_USERNAME", "your_bot_login")
    )
    model: str = field(default_factory=lambda: os.environ.get("MODEL", "ollama/gemma"))
    test_command: str = field(
        default_factory=lambda: os.environ.get("TEST_COMMAND", "./test.sh")
    )
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "vlooper.db")
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("MAX_RETRIES", "2"))
    )
    execution_timeout: int = field(
        default_factory=lambda: int(os.environ.get("EXECUTION_TIMEOUT", "300"))
    )
    loop_sleep_seconds: int = field(
        default_factory=lambda: int(os.environ.get("LOOP_SLEEP_SECONDS", "30"))
    )
    error_wait_seconds: int = field(
        default_factory=lambda: int(os.environ.get("ERROR_WAIT_SECONDS", "10"))
    )
    failed_task_cooldown_seconds: int = field(
        default_factory=lambda: int(
            os.environ.get("FAILED_TASK_COOLDOWN_SECONDS", "300")
        )
    )
    opencode_run_timeout: int = field(
        default_factory=lambda: int(os.environ.get("OPENCODE_RUN_TIMEOUT", "1800"))
    )
    test_run_timeout: int = field(
        default_factory=lambda: int(os.environ.get("TEST_RUN_TIMEOUT", "30"))
    )
    git_user_name: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_NAME", "AI OpenCode Bot")
    )
    git_user_email: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_EMAIL", "ai-bot@://github.com")
    )
    workspace_base_dir: str = field(
        default_factory=lambda: os.environ.get(
            "WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace")
        )
    )
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    log_file: str | None = field(
        default_factory=lambda: os.environ.get("LOG_FILE", None)
    )


config = Config()
