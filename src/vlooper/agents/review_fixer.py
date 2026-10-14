from typing import Any, Dict
import os
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient

logger = get_logger(__name__)

def review_fixer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: review_fixer
    Task: Reads PR comments from GitHub and applies requested refinements.
    """
    logger.info("[REVIEW_FIXER] Starting refinement process...")

    workspace_path = ctx.workspace_path
    pr_info = ""
    if ctx.pr_details:
        url = ctx.pr_details.get("html_url", "")
        pr_info = f"\n\nCONTEXT: You are working on Pull Request: {url}"

    # Use the provided action from the brief, or a sensible default
    base_action = brief.get("action", "Review the recent Pull Request comments for this task and apply the requested changes to the code.")

    # Augment the instruction with workspace awareness and specific tools instructions
    enhanced_instruction = (
        f"Your mission is to refine the code based on feedback from a Pull Request and then approve it once all requested changes are implemented.\n"
        f"**IMPORTANT: Your workspace directory is `{workspace_path}`**.\n"
        f"{pr_info}\n\n"
        "STEPS TO FOLLOW:\n"
        f"1. Use `cd {workspace_path} && gh pr view --comments` to read all the comments and feedback from the Pull Request.\n"
        "2. Analyze the requested changes thoroughly.\n"
        f"3. Apply the necessary fixes into the files within `{workspace_path}` using standard development tools (git, etc.).\n"
        "4. **CRITICAL: Once you are certain all issues have been addressed, YOU MUST APPROVE THE PR:**\n"
        f"   - Use command: `cd {workspace_path} && gh pr review --approve` \n"
        f"   - If you are reviewing your own Pull Request, use: `cd {workspace_path} && GH_TOKEN=${{GH_TOKEN_REVIEWER}} gh pr review --approve` \n\n"
        "5. Once finished, provide a brief summary of what you changed and confirm that you have approved the PR.\n\n"
        f"TASK: {base_action}"
    )

    client = OpencodeClient()
    try:
        # We execute the instruction. The model will call shell tools directly via opencode.
        result, err = client.run(enhanced_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[REVIEW_FIXER] Error executing refinement task: %s", err)
            return {"status": "failed", "error": err}

        logger.info("[REVIEW_FIXER] Refinement completed successfully.")
        return {
            "status": "success",
            "output": {"logs": result}
        }
    except Exception as e:
        logger.exception("[REVIEW_FIXER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}