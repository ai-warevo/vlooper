import re
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
    if ctx.pr_details:
        url = ctx.pr_details.get("html_url", "")
        pr_info = f"\n\nCONTEXT: You are reviewing Pull Request: {url}"
    
    action_instruction = (
        f"Your mission is to perform a professional code review of the current changes.\n"
        f"{pr_info}\n"
        "STEPS TO FOLLOW:\n"
        "1. Use `git diff` to see exactly what has changed in the workspace.\n"
        "2. Analyze the changes for bugs, security issues, or style inconsistencies.\n"
        "3. If you find any issues, write them down clearly in a file named `review_findings.txt`.\n"
        "4. Use the GitHub CLI to post these findings as comments on the Pull Request using the command:\n"
        "   `gh pr review --comment -F review_findings.txt`\n"
        "   (If you want to approve or request changes, use `--approve` or `--request-changes` flags instead of `--comment`).\n"
        "\n"
        "Once you have posted your comments/review via the CLI, provide a brief summary of what you did."
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