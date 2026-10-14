from typing import Any, Dict
from vlooper.infra.logger import get_logger
from vlooper.services.ai_service import generate_commit_message, generate_pr_metadata
from vlooper.services.git_service import cleanup_workspace, quick_reset

from vlooper.core.framework.context import TaskContext


logger = get_logger(__name__)


def github_pr_creator_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic executor for GitHub PR creation.
    Now composed of git_pusher and github_pr_manager agents for better modularity.
    """
    logger.info("[GITHUB_PR_CREATOR] Starting (composed) PR creation process...")

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
        # Importing locally to avoid potential circular dependencies during initialization
        from vlooper.agents.git_pusher import git_pusher_agent
        from vlooper.agents.github_pr_manager import github_pr_manager_agent

        # 2. Commit and Push (via git_pusher)
        logger.info("[GITHUB_PR_CREATOR] Generating commit message...")
        commit_msg = generate_commit_message(ctx.workspace_path, ctx.issue_number)
        
        logger.info("[GITHUB_PR_CREATOR] Delegating to git_pusher agent...")
        pusher_result = git_pusher_agent(ctx, {"commit_message": commit_msg})
        
        if pusher_result["status"] == "failed":
            raise Exception(f"Git Pusher failed: {pusher_result.get('error')}")

        # 3. Create Pull Request (via github_pr_manager)
        logger.info("[GITHUB_PR_CREATOR] Generating PR metadata...")
        pr_title, pr_body = generate_pr_metadata(
            ctx.workspace_path,
            ctx.issue_number,
            ctx.task_id,
            issue_title=ctx.issue_title,
            issue_body=ctx.issue_body,
        )

        logger.info("[GITHUB_PR_CREATOR] Delegating to github_pr_manager agent...")
        manager_result = github_pr_manager_agent(ctx, {
            "pr_title": pr_title, 
            "pr_body": pr_body
        })

        if manager_result["status"] == "failed":
            raise Exception(f"PR Manager failed: {manager_result.get('error')}")

        # Update context with PR details (handling both new and existing PR scenarios)
        pr_details = manager_result["output"]["pr_details"]
        ctx.pr_details = pr_details  # type: ignore

        logger.info("[GITHUB_PR_CREATOR] Pull Request process completed successfully!")

        # 4. Cleanup
        logger.info("[GITHUB_PR_CREATOR] Cleaning up workspace...")
        from vlooper.services.git_service import cleanup_workspace as _cleanup # To stay safe with shadow names if any, though not needed here
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
