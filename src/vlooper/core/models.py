"""Models used for tracking state and attempt information in the agent loop."""

from dataclasses import dataclass


@dataclass
class LoopState:
    """Контейнер для отслеживания состояния цикла Opencode."""

    ctx: str
    last_err_snip: str | None = None
    consecutive_errs: int = 0


@dataclass
class AttemptInfo:
    """TODO REPLACE_ME"""

    task_id: str
    attempt: int
    pre_attempt_status: str
    repo_dir: str
