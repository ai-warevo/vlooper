from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def coverage_booster_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: coverage_booster
    Task: Analyzes coverage reports and generates unit tests via LLM.
    """
    logger.info("[COVERAGE_BOOSTER] Starting coverage analysis/testing task...")

    # The mission brief should ideally contain instructions on which files need more coverage
    action_instruction = brief.get("action", "Identify files with low test coverage in the current directory and generate additional unit tests to increase it.")

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[COVERAGE_BOOSTER] Error executing coverage task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[COVERAGE_BOOSTER] Coverage boosting completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[COVERAGE_BOOSTER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}
