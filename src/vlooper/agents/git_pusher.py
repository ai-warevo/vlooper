from typing import Any, Dict
from vlooper.infra.logger import get_logger
from vlooper.services.git_service import commit_and_push
from vlooper.services.ai_service import generate_commit_message
from vlooper.core.framework.context import TaskContext


logger = get_logger(__name__)


def git_pusher_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Atomic agent for adding and pushing changes to the remote repository.
    If no commit message is provided in the brief, it generates one using AI.
    """
    logger.info("[GIT_PUSHER] Starting git push process...")

    if not ctx.workspace_path or not ctx.branch_name:
        logger.error("[GIT_PUSHER] Missing workspace_path or branch_name in context.")
        return {
            "status": "failed",
            "error": "Missing workspace_path or branch_name in context"
        }

    try:
        # 1. Resolve commit message
        commit_msg = brief.get("commit_message")
        if not commit_msg:
            logger.info("[GIT_PUSHER] No commit message provided in brief, generating one...")
            commit_msg = generate_commit_message(ctx.workspace_path, ctx.issue_number)
            if not commit_msg:
                return {
                    "status": "failed",
                    "error": "Failed to generate commit message"
                }

        # 2. Execute push
        logger.info("[GIT_PUSHER] Committing and pushing branch %s with message: %s", ctx.branch_name, commit_msg)
        commit_and_push(ctx.workspace_path, ctx.branch_name, commit_msg)

        return {
            "status": "success",
            "output": {
                "commit_message": commit_msg
            }
        }

    except Exception as e:
        logger.exception("[GIT_PUSHER] Failed to push changes")
        return {
            "status": "failed",
            "error": str(e)
        }
