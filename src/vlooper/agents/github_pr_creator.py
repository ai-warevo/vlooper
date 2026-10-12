from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def github_pr_creator_executor(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: github_pr_creator
    Task: Commits changes, pushes branches, and opens the final Pull Request via `gh`.
    """
    logger.info("[GITHUB_PR_CREATOR] Starting PR creation process...")

    action_instruction = brief.get("action", "Commit all current changes to the branch, push them to origin, and then create a Pull Request using the GitHub CLI (gh).")

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[GITHUB_PR_CREATOR] Error executing PR creation task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[GITHUB_PR_CREATOR] PR creation completed successfully.")
        return {
            "status": "success",
            "output": result
        }
    except Exception as e:
        logger.exception("[GITHUB_PR_CREATOR] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
