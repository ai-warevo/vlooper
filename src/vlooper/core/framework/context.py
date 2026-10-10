from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
    workspace_path: Optional[str] = None
    branch_name: Optional[str] = None
    exit_code: Optional[int] = None
    error_logs: Optional[str] = None
    is_aborted: bool = False
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
