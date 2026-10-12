from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def review_fixer_executor(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: review_fixer
    Task: Reads PR comments from GitHub and applies requested refinements.
    """
    logger.info("[REVIEW_FIXER] Starting refinement process...")

    action_instruction = brief.get("action", "Review the recent Pull Request comments for this task and apply the requested changes to the code.")

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[REVIEW_FIXER] Error executing refinement task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[REVIEW_FIXER] Refinement completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[REVIEW_FIXER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
