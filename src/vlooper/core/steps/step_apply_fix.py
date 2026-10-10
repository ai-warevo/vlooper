from ..framework.context import TaskContext
from ..framework.events import EventName
from vlooper.config import config
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import run_command

logger = get_logger(__name__)

def apply_ai_fix(ctx: TaskContext) -> None:
    """
    Triggers an automatic code fix using the Opencode agent based on error logs 
    provided in the context. This step only executes if tests have failed.
    """
    if ctx.exit_code == 0:
        # Tests passed, nothing to fix.
        return

    if not ctx.workspace_path:
        logger.error("❌ Cannot apply fix: ctx.workspace_path is not set.")
        ctx.is_aborted = True
        return

    logger.info("🤖 Attempting to apply AI-driven fix for task #%s...", ctx.task_id)

    # Emit event before invocation
    event_bus = ctx.metadata.get("event_bus")
    if event_bus:
        event_bus.emit(EventName.HARNESS_FIXING_CODE, {"task_id": ctx.task_id})

    if not ctx.error_logs:
        logger.warning("⚠️ Tests failed but no error logs were found in context.")
        return

    # The command we want to run: opencode run --model <model> <context/task_info>
    # We pass the string representation of ctx as it was in the original version.
    opencode_cmd = ["opencode", "run", "--model", config.model_cfg.model, str(ctx)]
    
    logger.debug("Executing Agent Command: %s", " ".join(opencode_cmd))

    try:
        # We run the command in the workspace directory
        _, err = run_command(
            opencode_cmd,
            cwd=ctx.workspace_path,
            timeout=config.timeouts.opencode_run_timeout,
            truncate_lines=50,
        )

        if err:
            # We don't necessarily want to abort the whole pipeline if the agent fails once, 
            # as the retry middleware might handle it. However, we log it clearly.
            logger.error("❌ Opencode agent failed to apply fix: %s", err)
            # If the agent itself crashes or cannot run, it's a hard failure for this attempt.
        else:
            logger.info("✅ AI agent has successfully completed the execution.")
            # Note: We do NOT change ctx.exit_code here. 
            # The next step/retry loop will RUN TESTS AGAIN to verify if the fix worked.

    except Exception as e:
        logger.exception("🚨 Critical error while running Opencode agent: %s", e)
        raise e
