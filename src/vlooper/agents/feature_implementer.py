from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)


def feature_implementer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: feature_implementer
    Task: Implements new features or requirements based on the issue description.
    """
    logger.info("[FEATURE_IMPLEMENTER] Starting implementation of new feature...")

    # The mission brief should contain the core requirement
    action_instruction = brief.get(
        "action", 
        f"Implement the requested feature described in the issue: {ctx.issue_title}. "
        f"Follow the requirements carefully and ensure the code is clean and well-documented."
    )

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[FEATURE_IMPLEMENTER] Error during implementation: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[FEATURE_IMPLEMENTER] Feature implementation completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[FEATURE_IMPLEMENTER] Unexpected error during implementation")
        return {"status": "error", "message": str(e)}
