"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger
from vlooper.services.github_service import get_github_author, post_github_comment

logger = get_logger(__name__)


class GitHubPickupHandler:
    """Handles posting a pickup notification to GitHub when an agent starts a task."""

    def handle(self, ctx: Any) -> None:
        """Posts a pickup comment to the GitHub issue/PR."""
        # Extract task data for the helper function
        task_data = {
            "repo_full_name": ctx.repo_full_name,
            "task_type": ctx.task_type,
            "branch_name": ctx.branch_name,  # Might be None
            "issue_number": ctx.issue_number,
        }

        try:
            # Fetch author to mention them
            author = get_github_author(task_data)
            mention = f"@{author} " if author and author != "assignee" else ""

            message = f"{mention} **vLooper has picked up this task.**"

            logger.info("Posting pickup comment to GitHub...")
            post_github_comment(task_data, message)

        except Exception as e:
            logger.error("Failed to post pickup comment to GitHub: %s", e)
