from vlooper.clients.github_client import get_issue_details
from vlooper.infra.logger import get_logger

from ..framework.context import TaskContext

logger = get_logger(__name__)


def fetch_issue_context(ctx: TaskContext) -> None:
    """
    Fetches issue details from GitHub and populates the context.
    Used to provide LLM agent with better understanding of the problem.
    """
    if not ctx.issue_number or ctx.issue_number == 0:
        return

    if not ctx.repo_full_name:
        logger.warning(
            "Cannot fetch issue details: repo_full_name is missing in context."
        )
        return

    try:
        logger.info("Fetching issue context for #%s...", ctx.issue_number)
        details = get_issue_details(ctx.issue_number, ctx.repo_full_name)
        if details:
            title, body, _ = details
            ctx.issue_title = title
            ctx.issue_body = body
            logger.info("Successfully fetched issue context.")
        else:
            logger.warning("Failed to fetch issue details for #%s.", ctx.issue_number)
    except Exception as e:
        logger.error("Error fetching issue context: %s", e)
