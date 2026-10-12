import json
import re
from typing import Any, Dict
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger
from vlooper.clients.opencode_client import OpencodeClient
from vlooper.services.github_service import post_github_comment

logger = get_logger(__name__)


def pr_reviewer_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: pr_reviewer
    Task: Performs automated code review/audit using LLM on git diffs.
    Returns findings as comments on GitHub.
    """
    logger.info("[PR_REVIEWER] Starting automated code review...")

    # Force the model to return a structured JSON format for easier parsing and posting
    action_instruction = (
        "Perform a thorough code review of the current changes (git diff). "
        "Look for bugs, security issues, or style inconsistencies. "
        "\n\n"
        "CRITICAL: You MUST respond ONLY with a JSON array of objects. Each object represents one finding.\n"
        "Schema: [{\"file\": \"path/to/file\", \"line\": 10, \"message\": \"description\"}]\n"
        "If no issues are found, return an empty array: []\n"
        "Do not include any conversational text, only the JSON array."
    )

    client = OpencodeClient()
    try:
        result_text, err = client.run(action_instruction, cwd=ctx.workspace_path)
        if err:
            logger.error("[PR_REVIEWER] Error executing review task: %s", err)
            return {"status": "failed", "error": err}

        # Try to extract JSON from the response (handling potential markdown blocks)
        findings = []
        try:
            json_match = re.search(r"\[\s*\{.*\}\s*\]", result_text, re.DOTALL)
            if json_match:
                findings = json.loads(json_match.group(0))
            else:
                # Fallback attempt to parse the whole text if no match found
                findings = json.loads(result_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("[PR_REVIEWER] Failed to parse LLM output as JSON. Raw output: %s. Error: %s", result_text, e)
            # If we can't parse it, we might treat the whole text as a single finding or just log error
            if result_text.strip():
                findings = [{"file": "N/A", "line": 0, "message": result_text.strip()}]

        # Prepare task data for commenting
        task_data = {
            "repo_full_name": ctx.repo_full_name,
            "task_type": "PR" if ctx.pr_details else "ISSUE",
            "branch_name": ctx.branch_name,
            "issue_number": ctx.issue_number,
        }

        # Post each finding as a separate comment on GitHub
        if findings:
            logger.info("[PR_REVIEWER] Found %d issues. Posting to GitHub...", len(findings))
            for finding in findings:
                file = finding.get("file", "Unknown file")
                line = finding.get("line", "N/A")
                msg = finding.get("message", "No description provided.")
                comment_body = f"### 🔍 Code Review Finding\n**File:** `{file}`\n**Line:** `{line}`\n\n{msg}"
                
                try:
                    post_github_comment(task_data, comment_body)
                except Exception as post_err:
                    logger.error("[PR_REVIEWER] Failed to post finding comment: %s", post_err)
            
            logger.info("[PR_REVIEWER] All findings posted successfully.")
        else:
            logger.info("[PR_REVIEWER] No issues found in code review.")

        logger.info("[PR_REVIEWER] Code review completed successfully.")
        return {
            "status": "success",
            "output": {"findings": findings, "logs": result_text}
        }
    except Exception as e:
        logger.exception("[PR_REVIEWER] Unexpected error during execution")
        return {"status": "error", "message": str(e)}