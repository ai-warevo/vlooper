"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger
from vlooper.services.github_service import get_github_author, post_github_comment

logger = get_logger(__name__)


class GitHubPickupHandler:
    """Handles posting a pickup notification to GitHub when an agent starts a task."""

    def handle(self, ctx: Any) -> None:
        """Posts a pickup comment to the GitHub issue/PR."""
        # Extract original task data from context
        task = ctx.metadata.get("original_task")
        if not task:
            logger.warning("Cannot post pickup comment: no original task in context.")
            return

        try:
            # Construct task data for the helper function
            # We use the actual task dict which has issue_number/branch_name
            task_data = {
                "repo_full_name": task["repo_full_name"],
                "task_type": task["task_type"],
                "branch_name": ctx.branch_name,  # Might be None
                "issue_number": task["issue_number"],
            }

            # Fetch author to mention them
            author = get_github_author(task_data)
            mention = f"@{author} " if author and author != "assignee" else ""

            message = f"{mention} **vLooper has picked up this task.**"

            logger.info("Posting pickup comment to GitHub...")
            post_github_comment(task_data, message)

        except Exception as e:
            logger.error("Failed to post pickup comment to GitHub: %s", e)
