from ..framework.context import TaskContext
from vlooper.logger import get_logger

logger = get_logger(__name__)

def apply_ai_fix(ctx: TaskContext) -> None:
    """
    Triggers an automatic code fix using the AI agent based on error logs 
    provided in the context. This step only executes if tests have failed.
    """
    if ctx.exit_code == 0:
        # Tests passed, nothing to fix.
        return

    logger.info("🤖 Attempting to apply AI-driven fix for task #%s...", ctx.task_id)

    # Emit event before invocation
    event_bus = ctx.metadata.get("event_bus")
    if event_bus:
        event_bus.emit("harness:fixing_code", {"task_id": ctx.task_id})

    if not ctx.error_logs:
        logger.warning("⚠️ Tests failed but no error logs were found in context.")
        return

    # Placeholder for OpenCode / Ollama integration logic.
    # In a real implementation, this would call the agent and wait for file writes.
    logger.info("🔍 Analyzing error logs...")
    
    # Simulate the process of an AI agent applying a fix
    # This is where you'd integrate `tools.opencode` or similar.
    logger.debug("Error Log Snippet: %s", ctx.error_logs[:200] + "...")

    # Mocking a successful "fix" application that would reset the exit code 
    # for the next retry loop iteration to attempt (though not actually rewriting files).
    # In reality, ApplyFix would write code, and then RetryLoop would call RunTests again.
    logger.info("🛠️ AI agent has applied suggested fixes to the workspace.")

    # Note: We do NOT change ctx.exit_code here because we want the 
    # retry middleware/next steps to actually RUN THE TESTS AGAIN 
    # to verify if the fix worked. We just indicate that an action was taken.
