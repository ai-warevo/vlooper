from typing import Any, Dict

from vlooper.agents.base import BaseAgent
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.services.github_service import post_github_comment

logger = get_logger(__name__)


class TelemetryAgent(BaseAgent):
    """Handles posting a success comment and telemetry when a Pull Request is created."""

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        """Posts a success comment to GitHub immediately after PR creation and logs telemetry."""
        task_id = ctx.task_id
        repo = ctx.repo_full_name
        branch = ctx.branch_name
        pr_details = ctx.pr_details

        logger.info("[TelemetryAgent] Posting success comment for Task #%s...", task_id)

        task_data = {
            "repo_full_name": repo,
            "task_type": "PR", 
            "branch_name": branch,
        }

        html_url = pr_details.get("html_url") if pr_details else ""
        message = (
            f"**vLooper Automation Complete!**\n\n"
            "The automated fix has been applied and a Pull Request "
            "has been created.\n\n"
            f"**Pull Request:** {html_url}" if html_url else ""
        ).strip()

        try:
            post_github_comment(task_data, message)
        except Exception as e:
            logger.error("[TelemetryAgent] Failed to post PR success comment: %s", e)

        # Also keep the telemetry
        logger.info(
            "[Telemetry] Task #%s: Pull Request created on %s (%s)",
            task_id,
            repo,
            branch,
        )

        return {"status": "success"}
