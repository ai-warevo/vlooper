from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def test_healer_executor(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: test_healer
    Task: Parses test error logs, identifies the root cause, and patches the code/tests.
    """
    logger.info("[TEST_HEALER] Starting failure analysis...")

    action_instruction = brief.get("action", "Analyze the provided test failures, identify the cause (in code or tests), and apply a fix to resolve them.")

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[TEST_HEALER] Error executing healing task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[TEST_HEALER] Healing completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[TEST_HEALER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
