"""Module documentation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskContext:
    """
    Represents the global mutable state that travels through the execution pipeline.
    This context encapsulates task primitives, execution artifacts, control flags,
    and arbitrary metadata.
    """

    # Core identity fields (extracted from database)
    task_id: str
    task_type: str  # ISSUE or PR
    issue_number: int
    repo_url: str
    repo_full_name: str | None = None
    branch_name: str | None = None

    # Execution state
    workspace_path: str
    exit_code: int | None = None
    is_aborted: bool = False
    error: Exception | None = None
    status: str = "PENDING"  # PENDING, CLAIMED, COMPLETED, FAILED

    # Extra information (parsed from meta)
    issue_title: str | None = None
    issue_body: str | None = None
    pr_details: dict[str, Any] | None = None

    # Dynamic context/runtime info
    metadata: dict[str, Any] = field(default_factory=dict)
