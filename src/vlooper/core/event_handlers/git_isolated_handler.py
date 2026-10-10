"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


class GitIsolatedHandler:
    """Handles telemetry/logging when a repository has been successfully isolated."""

    def handle(self, ctx_data: Any) -> None:
        """Handles the repository isolation event."""
        # pylint: disable=duplicate-code
        task_id = ctx_data.get("task_id")
        repo = ctx_data.get("repo")
        branch = ctx_data.get("branch")
        logger.info(
            "[Telemetry] Task #%s: Repository isolated on branch %s (%s)",
            task_id,
            branch,
            repo,
        )
