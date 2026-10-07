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
    lock_file_path: str = field(
        default_factory=lambda: os.environ.get("LOCK_FILE_PATH", "/tmp/vlooper.lock")
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("MAX_RETRIES", "2"))
    )
    execution_timeout: int = field(
        default_factory=lambda: int(os.environ.get("EXECUTION_TIMEOUT", "300"))
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
    loop_sleep_interval: int = field(
        default_factory=lambda: int(os.environ.get("LOOP_SLEEP_INTERVAL", "30"))
    )
    error_retry_interval: int = field(
        default_factory=lambda: int(os.environ.get("ERROR_RETRY_INTERVAL", "10"))
    )
    failed_task_cooldown_seconds: int = field(
        default_factory=lambda: int(
            os.environ.get("FAILED_TASK_COOLDOWN_SECONDS", "300")
        )
    )
    opencode_timeout: int = field(
        default_factory=lambda: int(os.environ.get("OPENCODE_TIMEOUT", "90"))
    )
    language: str = field(
        default_factory=lambda: os.environ.get("LANGUAGE", "en")
    )
    tests_timeout: int = field(
        default_factory=lambda: int(os.environ.get("TESTS_TIMEOUT", "30"))
    )
    max_opencode_attempts: int = field(
        default_factory=lambda: int(os.environ.get("MAX_OPENCODE_ATTEMPTS", "5"))
    )
    tui_update_interval: int = field(
        default_factory=lambda: int(os.environ.get("TUI_UPDATE_INTERVAL", "3"))
    )
    consecutive_error_threshold: int = field(
        default_factory=lambda: int(os.environ.get("CONSECUTIVE_ERROR_THRESHOLD", "2"))
    )
    log_truncation_lines: int = field(
        default_factory=lambda: int(os.environ.get("LOG_TRUNCATION_LINES", "50"))
    )
    error_snippet_lines: int = field(
        default_factory=lambda: int(os.environ.get("ERROR_SNIPPET_LINES", "15"))
    )
    output_truncate_lines: int = field(
        default_factory=lambda: int(os.environ.get("OUTPUT_TRUNCATE_LINES", "50"))
    )


config = Config()
