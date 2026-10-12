from typing import Any, Dict
from vlooper.infra.logger import get_logger
from vlooper.services.ai_service import generate_commit_message, generate_pr_metadata
from vlooper.services.git_service import cleanup_workspace, commit_and_push, quick_reset
from vlooper.services.github_service import create_pull_request_workflow

from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.events import EventName

logger = get_logger(__name__)


def github_pr_creator_executor(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic executor for GitHub PR creation.
    Uses reliable services instead of an LLM agent to prevent hallucinations.
    """
    logger.info("[GITHUB_PR_CREATOR] Starting deterministic PR creation process...")

    # 1. Safety check: Only proceed if tests passed
    if ctx.exit_code is not None and ctx.exit_code != 0:
        logger.info("[GITHUB_PR_CREATOR] Skipping PR creation; tests failed (exit code %s).", ctx.exit_code)
        return {
            "status": "success",
            "output": {"reason": "tests failed, skipping PR"}
        }

    if not ctx.workspace_path or not ctx.branch_name:
        logger.error("[GITHUB_PR_CREATOR] Cannot create PR: workspace_path or branch_name is missing.")
        return {
            "status": "failed",
            "error": "workspace_path or branch_name is missing from context"
        }

    repo_full_name = ctx.repo_full_name or ctx.metadata.get("repo_full_name")
    if not repo_full_name:
        logger.error("[GITHUB_PR_CREATOR] Cannot create PR: 'repo_full_name' not found.")
        return {
            "status": "failed",
            "error": "repo_full_name not found in context"
        }

    try:
        # 2. Commit and Push
        logger.info("[GITHUB_PR_CREATOR] Generating commit message...")
        commit_msg = generate_commit_message(ctx.workspace_path, ctx.issue_number)
        
        logger.info("[GITHUB_PR_CREATOR] Committing and pushing branch %s...", ctx.branch_name)
        commit_and_push(ctx.workspace_path, ctx.branch_name, commit_msg)

        # 3. Create Pull Request
        logger.info("[GITHUB_PR_CREATOR] Generating PR metadata...")
        pr_title, pr_body = generate_pr_metadata(
            ctx.workspace_path,
            ctx.issue_number,
            ctx.task_id,
            issue_title=ctx.issue_title,
            issue_body=ctx.issue_body,
        )

        logger.info("[GITHUB_PR_CREATOR] Opening Pull Request via GitHub CLI...")
        pr_details, err = create_pull_request_workflow(
            repo_full_name=repo_full_name,
            title=pr_title,
            body=pr_body,
            cwd=ctx.workspace_path,
        )

        if err:
            logger.error("[GITHUB_PR_CREATOR] GitHub CLI failed: %s", err)
            return {
                "status": "failed",
                "error": f"GitHub CLI error: {err}"
            }

        # Store details in context (as the original step did)
        ctx.pr_details = pr_details  # type: ignore

        logger.info("[GITHUB_PR_CREATOR] Pull Request created successfully!")

        # 4. Emit success event for orchestrator/handlers
        event_bus = ctx.metadata.get("event_bus")
        if event_bus:
            event_bus.emit(
                EventName.GITHUB_PR_CREATED,
                {
                    "task_id": ctx.task_id,
                    "repo": repo_full_name,
                    "branch": ctx.branch_name,
                    "details": pr_details,
                },
            )

        # 5. Cleanup
        logger.info("[GITHUB_PR_CREATOR] Cleaning up workspace...")
        cleanup_workspace(ctx.workspace_path, ctx.branch_name)

        return {
            "status": "success",
            "output": {
                "pr_details": pr_details,
                "commit_message": commit_msg
            }
        }

    except Exception as e:
        logger.exception("[GITHUB_PR_CREATOR] Unexpected error during PR workflow")
        # Recovery: quick reset the workspace to avoid leaving it in a broken state
        try:
            quick_reset(ctx.workspace_path)
        except Exception as cleanup_err:
            logger.error("[GITHUB_PR_CREATOR] Failed to perform quick reset after error: %s", cleanup_err)
            
        return {
            "status": "failed",
            "error": str(e)
        }
