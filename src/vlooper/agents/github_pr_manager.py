from typing import Any, Dict
from vlooper.infra.logger import get_logger
from vlooper.services.github_service import create_pull_request_workflow
from vlooper.clients.github_client import get_pr_details
from vlooper.core.framework.context import TaskContext


logger = get_logger(__name__)


def github_pr_manager_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Atomic agent for managing Pull Requests. 
    Checks if a PR already exists for the current branch; if so, returns its details.
    If no PR exists, creates one using provided metadata in the mission brief.
    """
    logger.info("[GITHUB_PR_MANAGER] Starting PR management process...")

    if not ctx.repo_full_name or not ctx.branch_name:
        logger.error("[GITHUB_PR_MANAGER] Missing repo_full_name or branch_name in context.")
        return {
            "status": "failed",
            "error": "Missing repo_full_name or branch_name in context"
        }

    try:
        # 1. Check for existing PR
        logger.info("[GITHUB_PR_MANAGER] Checking if a PR already exists for branch %s...", ctx.branch_name)
        existing_pr = get_pr_details(ctx.repo_full_name, ctx.branch_name)

        if existing_pr:
            num, title, body, _ = existing_pr
            logger.info("[GITHUB_PR_MANAGER] PR #%s already exists (Title: %s). Skipping creation.", num, title)
            return {
                "status": "success",
                "output": {
                    "pr_details": {
                        "number": num,
                        "title": title,
                        "body": body,
                        "html_url": f"https://github.com/{ctx.repo_full_name}/pull/{num}"
                    },
                    "reason": "already_exists"
                }
            }

        # 2. Create PR if it doesn't exist
        logger.info("[GITHUB_PR_MANAGER] No existing PR found. Creating one...")

        # Metadata retrieval from brief or context
        pr_title = brief.get("pr_title")
        pr_body = brief.get("pr_body")

        if not pr_title or not pr_body:
            logger.warning("[GITHUB_PR_MANAGER] No PR metadata provided in brief, attempting to use context.")
            # Fallback to context if possible (though as an atomic agent, we'd prefer it via brief)
            from vlooper.services.ai_service import generate_pr_metadata
            logger.info("[GITHUB_PR_MANAGER] Generating PR metadata using AI service...")
            pr_title, pr_body = generate_pr_metadata(
                ctx.workspace_path,
                ctx.issue_number,
                ctx.task_id,
                issue_title=ctx.issue_title,
                issue_body=ctx.issue_body,
            )

        if not pr_title or not pr_body:
             return {
                "status": "failed",
                "error": "Could not determine PR metadata (title/body)"
            }

        pr_details, err = create_pull_request_workflow(
            repo_full_name=ctx.repo_full_name,
            title=pr_title,
            body=pr_body,
            cwd=ctx.workspace_path,
        )

        if err:
            logger.error("[GITHUB_PR_MANAGER] GitHub CLI failed to create PR: %s", err)
            return {
                "status": "failed",
                "error": f"GitHub CLI error: {err}"
            }

        logger.info("[GITHUB_PR_MANAGER] Pull Request created successfully!")

        # Ensure pr_details is in the format expected by downstream (dict with html_url)
        if isinstance(pr_details, dict) and "html_url" in pr_details:
             output_pr_details = pr_details
        else:
             output_pr_details = {"html_url": pr_details}

        return {
            "status": "success",
            "output": {
                "pr_details": output_pr_details,
                "title": pr_title,
                "body": pr_body
            }
        }

    except Exception as e:
        logger.exception("[GITHUB_PR_MANAGER] Unexpected error during PR management")
        return {
            "status": "failed",
            "error": str(e)
        }
