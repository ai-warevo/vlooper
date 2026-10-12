from typing import Any, Dict
from vlooper.clients.opencode_client import OpencodeClient
from vlooper.clients.git_client import has_uncommitted_changes
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

    # In the new architecture, we check status from raw_input (passed via brief) or context
    raw_input = brief.get("raw_input", {})
    if raw_input.get("status") == "success" and raw_input.get("output", {}).get("exit_code") == 0:
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

    # Prefer logs from raw_input (passed from previous step) or fallback to context
    error_logs = ""
    if raw_input.get("status") in ["failed", "error"]:
        error_logs = raw_input.get("output", {}).get("logs", "")
    
    if not error_logs:
        error_logs = getattr(ctx, 'error_logs', "")
    
    if not error_logs:
        logger.warning("[AI_FIXER] No error logs were found in input or context.")
        return {
            "status": "failed",
            "error_message": "No error logs provided."
        }

    # Construct the prompt from the mission brief. 
    # The Synthesizer already includes a lot of info in 'mission_brief'.
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
         action_instruction += f"\nPREVIOUS TEST RUN FAILED (exit code: {raw_input.get('output', {}).get('exit_code', 'unknown')}).\nERROR LOGS:\n{error_logs}"

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
            # Verify if any changes were actually made
            changes_detected = has_uncommitted_changes(ctx.workspace_path)
            
            if not changes_detected:
                logger.info("[AI_FIXER] AI agent completed execution but no code changes were detected.")
                return {
                    "status": "success",
                    "output": {"applied": False, "reason": "no code changes detected"}
                }

            logger.info("[AI_FIXER] AI agent has successfully completed the execution and applied changes.")
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
