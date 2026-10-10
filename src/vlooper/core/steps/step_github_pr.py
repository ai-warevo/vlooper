from ..framework.context import TaskContext
from ..framework.types import StepFn
from ..framework.events import EventName
from vlooper.services.git_service import commit_and_push, quick_reset, cleanup_workspace
from vlooper.services.ai_service import generate_commit_message, generate_pr_metadata
from vlooper.services.github_service import create_pull_request_workflow
from vlooper.infra.logger import get_logger

logger = get_logger(__name__)

def github_create_pull_request(ctx: TaskContext) -> None:
    """
    Commits changes, pushes the branch, and opens an automated Pull Request via GitHub CLI.
    Only executes if tests have passed (ctx.exit_code == 0).
    """
    if ctx.exit_code != 0:
        logger.info("Skipping PR creation; tests failed or not run.")
        return

    if not ctx.workspace_path or not ctx.branch_name:
        logger.error("Cannot create PR: workspace_path or branch_name is missing from context.")
        ctx.is_aborted = True
        return

    # Use repo_full_name directly from context if available, fallback to metadata
    repo_full_name = ctx.repo_full_name or ctx.metadata.get("repo_full_name")
    if not repo_full_name:
        logger.error("Cannot create PR: 'repo_full_name' not found in context.")
        ctx.is_aborted = True
        return

    logger.info(" Preparing Pull Request for %s on branch %s...", repo_full_name, ctx.branch_name)

    try:
        # 1. Commit and Push
        commit_msg = generate_commit_message(ctx.workspace_path, ctx.issue_number)
        commit_and_push(ctx.workspace_path, ctx.branch_name, commit_msg)

        # 2. Create Pull Request
        logger.info("Using issue context from task for PR metadata...")
        
        pr_title, pr_body = generate_pr_metadata(
            ctx.workspace_path, 
            ctx.issue_number, 
            ctx.task_id,
            issue_title=ctx.issue_title,
            issue_body=ctx.issue_body
        )
        
        pr_details, err = create_pull_request_workflow(
            repo_full_name=repo_full_name,
            title=pr_title,
            body=pr_body,
            cwd=ctx.workspace_path
        )
        
        if err:
            raise Exception(f"GitHub CLI failed to create PR: {err}")
        
        # Store PR details in context for later use (e.g., commenting)
        ctx.pr_details = pr_details  # type: ignore

        logger.info("Pull Request created successfully!")

        # 3. Emit success event
        event_bus = ctx.metadata.get("event_bus")
        if event_bus:
            event_bus.emit(EventName.GITHUB_PR_CREATED, {
                "task_id": ctx.task_id,
                "repo": repo_full_name,
                "branch": ctx.branch_name,
                "details": ctx.pr_details
            })

        # Cleanup after successful PR creation
        cleanup_workspace(ctx.workspace_path, ctx.branch_name)

    except Exception as e:
        logger.exception("Failed to complete GitHub Pull Request workflow: %s", e)
        # Cleanup on failure: stash changes and return to main/master
        quick_reset(ctx.workspace_path)
        raise e
