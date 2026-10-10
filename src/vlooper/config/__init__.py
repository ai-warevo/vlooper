"""Configuration management for vlooper."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

from .git import GitConfig
from .model import ModelConfig
from .infra import InfraConfig
from .logs import LogConfig
from .timeouts import TimeoutConfig

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Config:
    """Configuration settings loaded from environment variables."""
    git: GitConfig = field(default_factory=GitConfig)
    model_cfg: ModelConfig = field(default_factory=ModelConfig)  # renamed to avoid collision
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
