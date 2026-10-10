"""Configuration management for vlooper."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class GitConfig:
    """Git related configuration."""
    org_name: str = field(
        default_factory=lambda: os.environ.get("ORG_NAME", "ai-warevo")
    )
    bot_username: str = field(
        default_factory=lambda: os.environ.get("BOT_USERNAME", "your_bot_login")
    )
    git_user_name: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_NAME", "AI OpenCode Bot")
    )
    git_user_email: str = field(
        default_factory=lambda: os.environ.get("GIT_USER_EMAIL", "ai-bot@://github.com")
    )
    gh_token: Optional[str] = field(
        default_factory=lambda: os.environ.get("GH_TOKEN", None)
    )


@dataclass
class ModelConfig:
    """Model related configuration."""
    model: str = field(
        default_factory=lambda: os.environ.get("MODEL", "ollama/gemma")
    )
    alt_model: Optional[str] = field(
        default_factory=lambda: os.environ.get("_MODEL", None)
    )


@dataclass
class InfraConfig:
    """Infrastructure related configuration."""
    test_command: str = field(
        default_factory=lambda: os.environ.get("TEST_COMMAND", "./test.sh")
    )
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "vlooper.db")
    )
    workspace_base_dir: str = field(
        default_factory=lambda: os.environ.get(
            "WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace")
        )
    )


@dataclass
class LogConfig:
    """Logging related configuration."""
    level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )
    file: Optional[str] = field(
        default_factory=lambda: os.environ.get("LOG_FILE", None)
    )


@dataclass
class TimeoutConfig:
    """Timeout related configuration."""
    max_task_retries: int = field(
        default_factory=lambda: int(os.environ.get("MAX_TASK_RETRIES", "2"))
    )
    max_pipeline_attempts: int = field(
        default_factory=lambda: int(os.environ.get("MAX_PIPELINE_ATTEMPTS", "5"))
    )
    execution_timeout: int = field(
        default_factory=lambda: int(os.environ.get("EXECUTION_TIMEOUT", "300"))
    )
    opencode_run_timeout: int = field(
        default_factory=lambda: int(os.environ.get("OPENCODE_RUN_TIMEOUT", "1800"))
    )
    test_run_timeout: int = field(
        default_factory=lambda: int(os.environ.get("TEST_RUN_TIMEOUT", "30"))
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


@dataclass
class Config:
    """Configuration settings loaded from environment variables."""
    git: GitConfig = field(default_factory=GitConfig)
    model_cfg: ModelConfig = field(default_factory=ModelConfig) # renamed to avoid collision
    infra: InfraConfig = field(default_factory=InfraConfig)
    logs: LogConfig = field(default_factory=LogConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)

    # Backward compatibility properties
    @property
    def org_name(self) -> str: return self.git.org_name
    @property
    def bot_username(self) -> str: return self.git.bot_username
    @property
    def model(self) -> str: return self.model_cfg.model
    @property
    def test_command(self) -> str: return self.infra.test_command
    @property
    def db_path(self) -> str: return self.infra.db_path
    @property
    def max_task_retries(self) -> int: return self.timeouts.max_task_retries
    @property
    def max_pipeline_attempts(self) -> int: return self.timeouts.max_pipeline_attempts
    @property
    def execution_timeout(self) -> int: return self.timeouts.execution_timeout
    @property
    def loop_sleep_seconds(self) -> int: return self.timeouts.loop_sleep_seconds
    @property
    def error_wait_seconds(self) -> int: return self.timeouts.error_wait_seconds
    @property
    def failed_task_cooldown_seconds(self) -> int: return self.timeouts.failed_task_cooldown_seconds
    @property
    def opencode_run_timeout(self) -> int: return self.timeouts.opencode_run_timeout
    @property
    def test_run_timeout(self) -> int: return self.timeouts.test_run_timeout
    @property
    def git_user_name(self) -> str: return self.git.git_user_name
    @property
    def git_user_email(self) -> str: return self.git.git_user_email
    @property
    def workspace_base_dir(self) -> str: return self.infra.workspace_base_dir
    @property
    def log_level(self) -> str: return self.logs.level
    @property
    def log_file(self) -> Optional[str]: return self.logs.file


config = Config()
