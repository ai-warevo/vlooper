import shlex
import subprocess
from ..framework.context import TaskContext
from ..framework.events import EventName
from vlooper.config import config
from vlooper.infra.logger import get_logger

logger = get_logger(__name__)

def run_repository_tests(ctx: TaskContext) -> None:
    """
    Executes the repository's local test harness using the configured command.
    Captured results are written back to the TaskContext.
    Emits a 'harness:test_passed' event if tests pass.
    """
    if not ctx.workspace_path:
        logger.error("❌ Cannot run tests: ctx.workspace_path is not set.")
        ctx.is_aborted = True
        return

    test_cmd = shlex.split(config.test_command)
    logger.info("🧪 Running repository tests in %s...", ctx.workspace_path)

    try:
        result = subprocess.run(
            test_cmd,
            cwd=ctx.workspace_path,
            capture_output=True,
            text=True,
            check=False  # We handle the exit code manually
        )

        ctx.exit_code = result.returncode
        ctx.error_logs = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

        if ctx.exit_code == 0:
            logger.info("✅ Tests passed successfully.")
            # Retrieve EventBus from context metadata to emit event
            event_bus = ctx.metadata.get("event_bus")
            if event_bus:
                event_bus.emit(EventName.HARNESS_TEST_PASSED, {"task_id": ctx.task_id})
        else:
            logger.warning("❌ Tests failed with exit code %d.", ctx.exit_code)
            logger.error("--- TEST FAILURE DETAILS ---\n%s\n-----------------------------", ctx.error_logs)

    except Exception as e:
        logger.exception("🚨 Critical error while running test harness: %s", e)
        ctx.exit_code = -1
        ctx.error_logs = str(e)
        ctx.is_aborted = True
