from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def linter_bot_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: linter_bot
    Task: Use linters (e.g., ruff) to find errors and applies fixes via OpenCode.
    """
    logger.info("[LINTER_BOT] Starting linting process...")

    # The mission brief is the instruction for the agent
    action_instruction = brief.get("action", "Run ruff check on the current directory, fix issues where possible, and report any remaining errors.")
    
    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[LINTER_BOT] Error executing linting task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[LINTER_BOT] Linting/fixing completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[LINTER_BOT] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
