import os
from ..framework.context import TaskContext
from ..framework.types import StepFn
from vlooper.services.git_service import prepare_repository, setup_working_branch
from vlooper.services.github_service import clone_repository_workflow
from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.logger import get_logger


logger = get_logger(__name__)

def _parse_repo_info(url: str) -> tuple[str, str]:
    """
    Parses a repository URL or full name to extract owner/repo and short name.
    Example input: 'https://github.com/owner/repo' -> ('owner/repo', 'repo')
    Example input: 'owner/repo' -> ('owner/repo', 'repo')
    """
    # Clean trailing .git if present
    clean_url = url.removesuffix(".git")
    
    # If it's a full URL, strip the protocol and domain
    if "://" in clean_url:
        parts = clean_url.split("/")
        # parts might be ['https:', '', 'github.com', 'owner', 'repo']
        if len(parts) >= 5:
            full_name = f"{parts[3]}/{parts[4]}"
            short_name = parts[4]
            return full_name, short_name
        else:
             raise VLooperError(f"Could not parse repository info from URL: {url}")
    else:
        # It's already in 'owner/repo' format
        parts = clean_url.split("/")
        if len(parts) == 2:
            return clean_url, parts[1]
        raise VLooperError(f"Could not parse repository info from: {url}")

def git_isolate_repository(ctx: TaskContext) -> None:
    """
    Clones the target repository locally and sets up a dedicated workspace branch.
    Prepares the context with 'workspace_path' and 'branch_name'.
    """
    # Identify task type from original record
    task_type = ctx.metadata["original_task"]["task_type"]
    logger.info("🚀 Isolating repository for %s #%s...", task_type.lower(), ctx.issue_number)

    try:
        full_name, short_name = _parse_repo_info(ctx.repo_url)
        
        # Determine branch name: 
        # Issues get a new standardized fix branch.
        # PRs use the existing head branch captured by the scanner.
        if task_type == "ISSUE":
            branch_name = f"vlooper/fix-{ctx.issue_number}"
        else:
            branch_name = ctx.branch_name
        
        # Determine if we should skip reset (for retry attempts)
        attempt_count = ctx.metadata.get("attempt_count", 0)
        skip_reset = attempt_count > 1

        # Determine working directory
        base_dir = os.path.expanduser(config.workspace_base_dir)
        os.makedirs(base_dir, exist_ok=True)
        repo_dir = os.path.join(base_dir, short_name)

        # 1. Clone and/or prepare directory
        if not os.path.exists(repo_dir):
            logger.info("📥 Cloning repository %s into %s...", full_name, repo_dir)
            success, err = clone_repository_workflow(full_name, short_name, base_dir)
            if not success:
                raise VLooperError(f"Failed to clone repository: {err}")
        else:
            # If it exists, we prepare its state (reset/pull) via git_service
            prepare_repository(repo_dir, skip_reset=skip_reset)
        
        # 2. Set up the new feature branch
        setup_working_branch(repo_dir, branch_name, task_type=task_type)
        
        # Update context
        ctx.workspace_path = repo_dir
        ctx.branch_name = branch_name
        ctx.metadata["repo_full_name"] = full_name

        # Emit success event
        event_bus = ctx.metadata.get("event_bus")
        if event_bus:
            event_bus.emit("git:isolated", {
                "task_id": ctx.task_id,
                "repo": full_name,
                "branch": branch_name,
                "workspace": repo_dir
            })
        
        logger.info("✅ Repository isolated at %s on branch %s (Attempt: %d)", repo_dir, branch_name, attempt_count)

    except Exception as e:
        logger.exception("❌ Failed to isolate repository: %s", e)
        raise e
