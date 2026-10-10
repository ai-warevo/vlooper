from typing import Any
from vlooper.infra.logger import get_logger

logger = get_logger(__name__)

class PrCreatedHandler:
    """Handles telemetry/logging when a Pull Request has been successfully created."""
    def handle(self, ctx_data: Any) -> None:
        task_id = ctx_data.get("task_id")
        repo = ctx_data.get("repo")
        branch = ctx_data.get("branch")
        logger.info("[Telemetry] 🚀 Task #%s: Pull Request created on %s (%s)", task_id, repo, branch)
