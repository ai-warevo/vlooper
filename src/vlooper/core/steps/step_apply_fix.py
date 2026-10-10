"""Module documentation."""

from vlooper.clients.opencode_client import OpencodeClient
from vlooper.config import config
from vlooper.infra.logger import get_logger

from ..framework.context import TaskContext
from ..framework.events import EventName

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
        logger.error("Cannot apply fix: ctx.workspace_path is not set.")
        ctx.is_aborted = True
        return

    logger.info("Attempting to apply AI-driven fix for task #%s...", ctx.task_id)

    # Emit event before invocation
    event_bus = ctx.metadata.get("event_bus")
    if event_bus:
        event_bus.emit(EventName.HARNESS_FIXING_CODE, {"task_id": ctx.task_id})

    if not ctx.error_logs:
        logger.warning("Tests failed but no error logs were found in context.")
        return

    # The command we want to run: opencode run --model <model> <context/task_info>
    client = OpencodeClient()
    logger.debug("Executing Agent Command via client for task #%s", ctx.task_id)

    # Construct a clean prompt for the agent with issue context if available and STRICT instructions
    prompt_parts = [
        (
            f"Fix issue #{ctx.issue_number} (Task {ctx.task_id}) in repo "
            f"{ctx.repo_full_name or ctx.repo_url} on branch "
            f"'{ctx.branch_name or 'unknown'}'."
        ),
        (
            "\nIMPORTANT: DO NOT use 'git commit', 'git push', "
            "or any other git commands to save your work."
        ),
        "Only modify the necessary files to fix the issue.",
        "The system will handle committing and pushing your changes automatically.",
    ]

    if ctx.issue_title:
        prompt_parts.append(f"\nISSUE TITLE: {ctx.issue_title}")
    if ctx.issue_body:
        prompt_parts.append(f"\nISSUE DESCRIPTION:\n{ctx.issue_body}")

    prompt_parts.append(f"\nPREVIOUS TEST RUN FAILED (exit code: {ctx.exit_code}).")
    prompt_parts.append(f"ERROR LOGS:\n{ctx.error_logs}")

    prompt = "\n".join(prompt_parts)

    try:
        # We run the command in the workspace directory
        _, err = client.run(
            prompt,
            cwd=ctx.workspace_path,
            timeout=config.timeouts.opencode_run_timeout,
            truncate_lines=50,
        )

        if err:
            # We don't necessarily want to abort the whole pipeline if the agent fails once,
            # as the retry middleware might handle it. However, we log it clearly.
            logger.error("Opencode agent failed to apply fix: %s", err)
            # If the agent itself crashes or cannot run, it's a hard failure for this attempt.
        else:
            logger.info("AI agent has successfully completed the execution.")
            # Note: We do NOT change ctx.exit_code here.
            # The next step/retry loop will RUN TESTS AGAIN to verify if the fix worked.

    except Exception:
        logger.exception("Critical error while running Opencode agent")
        raise
