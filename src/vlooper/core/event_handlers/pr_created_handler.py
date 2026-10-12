"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


from typing import Any

from vlooper.infra.logger import get_logger
from vlooper.services.github_service import post_github_comment


logger = get_logger(__name__)


class PrCreatedHandler:
    """Handles posting a success comment when a Pull Request is created."""

    def handle(self, ctx_data: Any) -> None:
        """Posts a success comment to GitHub immediately after PR creation."""
        task_id = ctx_data.get("task_id")
        repo = ctx_data.get("repo")
        branch = ctx_data.get("branch")
        pr_details = ctx_data.get("details")

        logger.info("[PrCreatedHandler] Posting success comment for Task #%s...", task_id)

        task_data = {
            "repo_full_name": repo,
            "task_type": "PR", 
            "branch_name": branch,
        }

        message = (
            f"**vLooper Automation Complete!**\n\n"
            "The automated fix has been applied and a Pull Request "
            "has been created.\n\n"
            f"**Pull Request:** {pr_details.get('html_url')}"
        )

        try:
            post_github_comment(task_data, message)
        except Exception as e:
            logger.error("[PrCreatedHandler] Failed to post PR success comment: %s", e)

        # Also keep the telemetry
        logger.info(
            "[Telemetry] Task #%s: Pull Request created on %s (%s)",
            task_id,
            repo,
            branch,
        )
