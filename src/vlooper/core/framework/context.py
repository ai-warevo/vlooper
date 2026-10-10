from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskContext:
    """
    Represents the global mutable state that travels through the execution pipeline.
    This context encapsulates task primitives, execution artifacts, control flags,
    and arbitrary metadata.
    """

    task_id: str
    issue_number: int
    repo_url: str
    repo_full_name: str | None = None
    branch_name: str | None = None
    exit_code: int | None = None
    error_logs: str | None = None
    is_aborted: bool = False
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    issue_title: str | None = None
    issue_body: str | None = None
