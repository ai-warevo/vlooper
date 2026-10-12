from typing import Any, Dict
from vlooper.clients.github_client import get_issue_details
from vlooper.infra.logger import get_logger

from vlooper.core.framework.context import TaskContext

logger = get_logger(__name__)


def issue_fetcher_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: issue_fetcher
    Task: Fetches issue details from GitHub and returns them as a structured JSON object.
    Returns: output containing title and body.
    """
    logger.info("[ISSUE_FETCHER] Starting issue context fetch...")

    if not ctx.issue_number or ctx.issue_number == 0:
        return {
            "status": "failed",
            "error_message": "Missing issue number in context."
        }

    if not ctx.repo_full_name:
        logger.warning("[ISSUE_FETCHER] repo_full_name is missing in context.")
        return {
            "status": "failed",
            "error_message": "repo_full_name is missing in context."
        }

    try:
        details = get_issue_details(ctx.issue_number, ctx.repo_full_name)
        if details:
            title, body, _ = details
            # Update context for continuity
            ctx.issue_title = title
            ctx.issue_body = body
            
            logger.info("[ISSUE_FETCHER] Successfully fetched issue context.")
            return {
                "status": "success",
                "output": {
                    "title": title,
                    "body": body
                }
            }
        else:
            logger.warning("[ISSUE_FETCHER] Failed to fetch issue details for #%s.", ctx.issue_number)
            return {
                "status": "failed",
                "error_message": f"Could not fetch details for issue #{ctx.issue_number}"
            }
    except Exception as e:
        logger.exception("[ISSUE_FETCHER] Error fetching issue context")
        return {
            "status": "failed",
            "error_message": str(e)
        }
