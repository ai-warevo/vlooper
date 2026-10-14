import re
import os
from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)


def pr_reviewer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: pr_reviewer
    Task: Performs automated code review using LLM and GitHub CLI.
    The agent is instructed to use shell tools (git, gh) to perform the review.
    """
    logger.info("[PR_REVIEWER] Starting automated code review...")

    # Prepare context for the LLM
    pr_info = ""
    workspace_path = ctx.workspace_path
    findings_file_abs = os.path.join(workspace_path, "review_findings.txt")
    
    if ctx.pr_details:
        url = ctx.pr_details.get("html_url", "")
        pr_info = f"\n\nCONTEXT: You are reviewing Pull Request: {url}"
    
    action_instruction = (
        f"Your mission is to perform a professional code review of the current changes.\n"
        f"**IMPORTANT: Your workspace directory is `{workspace_path}`**.\n\n"
        f"{pr_info}\n"
        f"STEPS TO FOLLOW:\n"
        f"1. Use `git -C {workspace_path} diff` to see exactly what has changed in the workspace.\n"
        f"2. Analyze the changes for bugs, security issues, or style inconsistencies.\n"
        f"3. Write your findings clearly into this EXACT file path: `{findings_file_abs}`\n"
        f"4. **CRITICAL: You MUST select the correct GitHub CLI flag based on your conclusion and run it from within `{workspace_path}`:**\n"
        f"   - If you decide to APPROVE the PR $\rightarrow$ use command: `cd {workspace_path} && gh pr review --approve -F {findings_file_abs}`\n"
        f"   - If you decide to REQUEST CHANGES $\rightarrow$ use command: `cd {workspace_path} && gh pr review --request-changes -F {findings_file_abs}`\n"
        f"   - For any other type of feedback (comment only) $\rightarrow$ use command: `cd {workspace_path} && gh pr review --comment -F {findings_file_abs}`\n"
        f"\n"
        f"**IMPORTANT NOTE FOR REVIEWS:**\n"
        f"If you are reviewing your own Pull Request, the standard `GH_TOKEN` will fail. "
        f"In that case, prefix your review command with the reviewer token variable like this:\n"
        f"`cd {workspace_path} && GH_TOKEN=${{GH_TOKEN_REVIEWER}} gh pr review ...` (using the appropriate flag).\n\n"
        f"Your verdict in the text MUST match the flag you use in the CLI command.\n"
        f"Once you have posted your comments/review via the CLI, provide a brief summary of what you did."
    )

    client = OpencodeClient()
    try:
        # We execute the instruction. The model will call shell tools directly via opencode.
        result_text, err = client.run(action_instruction, cwd=ctx.workspace_path)
        
        if err:
            logger.error("[PR_REVIEWER] Error during execution: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[PR_REVIEWER] Code review process completed.")
        return {
            "status": "success",
            "output": {"logs": result_text}
        }
    except Exception as e:
        logger.exception("[PR_REVIEWER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}