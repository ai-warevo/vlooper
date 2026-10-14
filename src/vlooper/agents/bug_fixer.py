from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)


def bug_fixer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: bug_fixer
    Task: Analyzes test failures and fixes the underlying business logic/code.
    """
    logger.info("[BUG_FIXER] Starting business logic repair...")

    # The mission brief should contain the error logs or context
    action_instruction = brief.get(
        "action",
        f"Analyze the following test failures and fix the underlying code logic: {ctx.error_logs}. "
        f"Ensure that the implementation correctly follows the requirements in the issue title: {ctx.issue_title}."
    )

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[BUG_FIXER] Error during bug fixing: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[BUG_FIXER] Bug fix completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[BUG_FIXER] Unexpected error during bug fixing")
        return {"status": "error", "message": str(e)}
