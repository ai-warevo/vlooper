from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def test_healer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: test_healer
    Task: Fixes broken tests, environment issues, or flaky testing infrastructure.
    """
    logger.info("[TEST_HEALER] Starting test/environment healing...")

    # The mission brief should contain instructions on what is wrong with the tests
    action_instruction = brief.get(
        "action",
        f"The tests are failing due to infrastructure or test-code issues, not business logic. "
        f"Analyze these logs: {ctx.error_logs}. Fix the test files or environment (e.g., missing dependencies, incorrect assertions in tests) so that they can run reliably."
    )

    client = OpencodeClient()
    try:
        result, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[TEST_HEALER] Error during test healing: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[TEST_HEALER] Test healing completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[TEST_HEALER] Unexpected error during test healing")
        return {"status": "error", "message": str(e)}
