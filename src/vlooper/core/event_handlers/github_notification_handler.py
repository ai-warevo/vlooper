"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger
from vlooper.services.github_service import get_github_author, post_github_comment

logger = get_logger(__name__)


class GitHubNotificationHandler:
    """Handles posting summary comments to GitHub issues/PRs after pipeline completion."""

    def handle(self, ctx: Any) -> None:
        """Posts a summary comment to the GitHub issue/PR after pipeline completion."""
        # Construct task data for the legacy helper function
        task_data = {
            "repo_full_name": ctx.metadata.get("repo_full_name"),
            "task_type": ctx.metadata["original_task"]["task_type"],
            "branch_name": ctx.branch_name,
        }

        # Ensure we have the necessary info to identify the issue/PR
        if not task_data["repo_full_name"] or not task_data["branch_name"]:
            logger.warning(
                "Cannot post GitHub comment: missing repo_full_name or branch_name in context."
            )
            return

        try:
            # Fetch author to mention them
            author = get_github_author(task_data)
            mention = f"@{author} " if author and author != "assignee" else ""

            if ctx.exit_code == 0:
                # Successful completion
                message = (
                    f"{mention} **vLooper Automation Complete!**\n\n"
                    "The automated fix has been applied and a Pull Request "
                    "has been created."
                )
                if hasattr(ctx, "pr_details") and ctx.pr_details:
                    url = ctx.pr_details.get("html_url", "")
                    if url:
                        message += f"\n\n**Pull Request:** {url}"

                logger.info("Posting success comment to GitHub...")
                post_github_comment(task_data, message)
            else:
                # Failure (either aborted or exit code != 0)
                error_msg = (
                    str(ctx.error)
                    if ctx.error
                    else f"Pipeline failed with exit code {ctx.exit_code}"
                )
                message = (
                    f"{mention} **vLooper Automation Failed**\n\n"
                    "An error occurred during the automated cycle:\n"
                    f"`{error_msg}`"
                )

                logger.info("Posting failure comment to GitHub...")
                post_github_comment(task_data, message)

        except Exception as e:
            logger.error("Failed to post completion comment to GitHub: %s", e)
