from typing import Any, Dict
import os

from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.infra.logger import get_logger
from vlooper.services.git_service import prepare_repository, setup_working_branch
from vlooper.services.github_service import clone_repository_workflow

from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.events import EventName

logger = get_logger(__name__)


def git_isolator_agent(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role: git_isolator
    Task: Clones the target repository locally and sets up a dedicated workspace branch.
    Returns: output containing workspace_path, branch_name, and repo_full_name.
    """
    logger.info("[GIT_ISOLATOR] Starting repository isolation...")

    # Identify task type from original record (passed via metadata in context)
    task_type = ctx.task_type
    
    try:
        # We can use the brief or the context. Let's rely on context as before but honor the structure.
        # The original code used ctx.repo_url, which should be in TaskContext.
        
        def _parse_repo_info(url: str) -> tuple[str, str]:
            clean_url = url.removesuffix(".git")
            if "://" in clean_url:
                parts = clean_url.split("/")
                if len(parts) >= 5:
                    full_name = f"{parts[3]}/{parts[4]}"
                    short_name = parts[4]
                    return full_name, short_name
                raise VLooperError(f"Could not parse repository info from URL: {url}")
            parts = clean_url.split("/")
            if len(parts) == 2:
                return clean_url, parts[1]
            raise VLooperError(f"Could not parse repository info from: {url}")

        full_name, short_name = _parse_repo_info(ctx.repo_url)

        # Determine branch name
        if task_type == "ISSUE":
            branch_name = f"vlooper/fix-{ctx.issue_number}"
        else:
            branch_name = ctx.branch_name or ""

        attempt_count = ctx.metadata.get("attempt_count", 0)
        skip_reset = attempt_count > 1

        base_dir = os.path.expanduser(config.infra.workspace_base_dir)
        os.makedirs(base_dir, exist_ok=True)
        repo_dir = os.path.join(base_dir, short_name)

        if not os.path.exists(repo_dir):
            logger.info("[GIT_ISOLATOR] Cloning repository %s into %s...", full_name, repo_dir)
            success, err = clone_repository_workflow(full_name, short_name, base_dir)
            if not success:
                raise VLooperError(f"Failed to clone repository: {err}")
        else:
            prepare_repository(repo_dir, skip_reset=skip_reset)

        setup_working_branch(repo_dir, branch_name, task_type=task_type)

        # Update context (important for subsequent steps in the same execution run if the orchestrator uses it)
        ctx.workspace_path = repo_dir
        ctx.branch_name = branch_name
        ctx.repo_full_name = full_name
        ctx.metadata["repo_full_name"] = full_name

        # Emit success event
        event_bus = ctx.metadata.get("event_bus")
        if event_bus:
            event_bus.emit(
                EventName.GIT_ISOLATED,
                {
                    "task_id": ctx.task_id,
                    "repo": full_name,
                    "branch": branch_name,
                    "workspace": repo_dir,
                },
            )

        logger.info("[GIT_ISOLATOR] Repository isolated successfully at %s", repo_dir)
        
        return {
            "status": "success",
            "output": {
                "workspace_path": repo_dir,
                "branch_name": branch_name,
                "repo_full_name": full_name
            }
        }

    except Exception as e:
        logger.exception("[GIT_ISOLATOR] Failed to isolate repository")
        return {
            "status": "failed",
            "error_message": str(e)
        }
