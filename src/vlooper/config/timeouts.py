"""Configuration for timeouts."""

import os
from dataclasses import dataclass, field


@dataclass
class TimeoutConfig:
    """Timeout related configuration."""

    # pylint: disable=too-many-instance-attributes

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
