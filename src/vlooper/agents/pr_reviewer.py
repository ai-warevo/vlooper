from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def pr_reviewer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: pr_reviewer
    Task: Performs automated code review/audit using LLM on git diffs.
    """
    logger.info("[PR_REVIEWER] Starting automated code review...")

    action_instruction = brief.get("action", "Perform a thorough code review of the current changes (git diff). Look for bugs, security issues, and style inconsistencies.")

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[PR_REVIEWER] Error executing review task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[PR_REVIEWER] Code review completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[PR_REVIEWER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
