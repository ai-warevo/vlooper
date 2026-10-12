import shlex
import subprocess
from typing import Any, Dict

from vlooper.config import config
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import filter_test_logs

from vlooper.core.framework.context import TaskContext


logger = get_logger(__name__)


def test_runner_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: test_runner
    Task: Executes the repository's local test harness and returns detailed results.
    Returns: output containing exit_code and logs.
    """
    logger.info("[TEST_RUNNER] Starting test execution...")

    if not ctx.workspace_path:
        logger.error("[TEST_RUNNER] Cannot run tests: ctx.workspace_path is not set.")
        return {
            "status": "failed",
            "error_message": "ctx.workspace_path is not set."
        }

    test_cmd = shlex.split(config.infra.test_command)
    logger.info("[TEST_RUNNER] Running command: %s in %s", ' '.join(test_cmd), ctx.workspace_path)

    try:
        result = subprocess.run(
            test_cmd,
            cwd=ctx.workspace_path,
            capture_output=True,
            text=True,
            check=False,
        )

        exit_code = result.returncode
        raw_logs = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        filtered_logs = filter_test_logs(raw_logs)

        # Update context
        ctx.exit_code = exit_code
        ctx.error_logs = filtered_logs

        if exit_code == 0:
            logger.info("[TEST_RUNNER] Tests passed successfully.")
            
            return {
                "status": "success",
                "output": {
                    "exit_code": exit_code,
                    "logs": filtered_logs
                }
            }
        else:
            logger.warning("[TEST_RUNNER] Tests failed with exit code %d.", exit_code)
            return {
                "status": "failed",
                "output": {
                    "exit_code": exit_code,
                    "logs": filtered_logs
                }
            }

    except Exception as e:
        logger.exception("[TEST_RUNNER] Critical error while running test harness")
        return {
            "status": "failed",
            "error_message": str(e)
        }
