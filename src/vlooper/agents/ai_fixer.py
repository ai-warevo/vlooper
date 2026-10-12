from typing import Any, Dict
from vlooper.clients.opencode_client import OpencodeClient
from vlooper.config import config
from vlooper.infra.logger import get_logger

from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.events import EventName

logger = get_logger(__name__)


def ai_fixer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: ai_fixer
    Task: Take error logs or linting errors from the brief and apply fixes via OpenCode.
    Returns: output indicating success/failure of application attempt.
    """
    logger.info("[AI_FIXER] Starting AI fix attempt...")

    # In the new architecture, we check status from context if available
    if getattr(ctx, 'exit_code', 0) == 0:
        logger.info("[AI_FIXER] Tests passed, nothing to fix.")
        return {
            "status": "success",
            "output": {"applied": False, "reason": "tests already passing"}
        }

    if not ctx.workspace_path:
        logger.error("[AI_FIXER] Cannot apply fix: ctx.workspace_path is not set.")
        return {
            "status": "failed",
            "error_message": "ctx.workspace_path is not set."
        }

    event_bus = ctx.metadata.get("event_bus")
    if event_bus:
        event_bus.emit(EventName.HARNESS_FIXING_CODE, {"task_id": ctx.task_id})

    error_logs = getattr(ctx, 'error_logs', "")
    if not error_logs:
        logger.warning("[AI_FIXER] Tests failed but no error logs were found in context.")
        return {
            "status": "failed",
            "error_message": "No error logs provided in context."
        }

    # Construct the prompt from the mission brief or fall back to manual construction if needed.
    # The system is supposed to provide a condensed 'action' instruction in the brief.
    action_instruction = brief.get("action")
    if not action_instruction:
         logger.warning("[AI_FIXER] No specific action instruction found in mission brief. Constructing fallback.")
         action_instruction = (
             f"Fix issue #{ctx.issue_number} (Task {ctx.task_id}) in repo "
             f"{ctx.repo_full_name or ctx.repo_url} on branch "
             f"'{ctx.branch_name or 'unknown'}'."
         )
         action_instruction += "\nIMPORTANT: DO NOT use 'git commit', 'git push', 'or any other git commands to save your work.\"\nOnly modify necessary files."
         if ctx.issue_title: action_instruction += f"\nISSUE TITLE: {ctx.issue_title}"
         if ctx.issue_body: action_instruction += f"\nISSUE DESCRIPTION:\n{ctx.issue_body}"
         action_instruction += f"\nPREVIOUS TEST RUN FAILED (exit code: {ctx.exit_code}).\nERROR LOGS:\n{error_logs}"

    client = OpencodeClient()
    logger.debug("[AI_FIXER] Executing Agent Command via client for task #%s", ctx.task_id)

    try:
        _, err = client.run(
            action_instruction,
            cwd=ctx.workspace_path,
            timeout=config.timeouts.opencode_run_timeout,
            truncate_lines=50,
        )

        if err:
            logger.error("[AI_FIXER] Opencode agent failed to apply fix: %s", err)
            return {
                "status": "failed",
                "error_message": err
            }
        else:
            logger.info("[AI_FIXER] AI agent has successfully completed the execution.")
            return {
                "status": "success",
                "output": {"applied": True}
            }

    except Exception as e:
        logger.exception("[AI_FIXER] Critical error while running Opencode agent")
        return {
            "status": "failed",
            "error_message": str(e)
        }
