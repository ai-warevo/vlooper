"""Service for orchestrating Git operations and high-level workspace management."""

from vlooper.clients.git_client import (
    add_all,
    checkout,
    clean_files,
    commit,
    create_branch,
    delete_branch,
    get_default_branch,
    has_uncommitted_changes,
    is_remote_branch_exists,
    pull,
    push,
    reset_hard,
    stash,
)
from vlooper.core.exceptions import VLooperError
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import run_command

logger = get_logger(__name__)


def prepare_repository(repo_dir, skip_reset=False):
    """Prepares an existing repository: resets to default branch and pulls."""
    if skip_reset:
        logger.info("Skipping reset for existing workspace.")
        return

    logger.info("Resetting workspace to default branch...")
    try:
        default_branch = get_default_branch(repo_dir)
        checkout(repo_dir, default_branch, force=True)
        pull(repo_dir, "origin", default_branch)
    except VLooperError as e:
        logger.warning("Reset/Pull failed, proceeding with existing state: %s", e)


def setup_working_branch(repo_dir, branch_name, task_type):
    """Prepares a new git branch for the given task."""
    logger.info("Preparing branch %s...", branch_name)
    try:
        checkout(repo_dir, branch_name, force=True)
    except VLooperError as e:
        if task_type == "ISSUE":
            logger.info(
                "Creating new issue branch %s from default branch...", branch_name
            )
            default_branch = get_default_branch(repo_dir)
            create_branch(repo_dir, branch_name, start_point=default_branch)
        else:
            raise VLooperError(
                f"Could not find or create branch {branch_name}: {e}"
            ) from e

    if task_type == "PR":
        logger.info("Pulling remote branch %s...", branch_name)
        success, err = pull(repo_dir, "origin", branch_name)
        if not success:
            raise VLooperError(f"Failed to pull remote branch {branch_name}: {err}")
    return True


def commit_and_push(
    repo_dir,
    branch_name,
    commit_msg,
    user_name: str | None = None,
    user_email: str | None = None,
):
    """Orchestrates committing changes and pushing with a rebase strategy."""
    # 1. Commit
    if has_uncommitted_changes(repo_dir):
        logger.info("Finalizing changes...")
        add_all(repo_dir)
        commit(repo_dir, commit_msg, user_name=user_name, user_email=user_email)
    else:
        logger.info("No uncommitted changes found. Skipping redundant commit.")

    # 2. Check if remote exists for smart rebase
    if is_remote_branch_exists(repo_dir, branch_name):
        logger.info("Remote branch found. Attempting rebase...")
        success, err = pull(repo_dir, "origin", branch_name, rebase=True)
        if not success:
            raise VLooperError(f"Rebase failed/conflict detected: {err}")
    else:
        logger.info("First push for branch %s.", branch_name)

    # 3. Push
    push(repo_dir, branch_name)
    return True


def cleanup_workspace(repo_dir, branch_name):
    """Full cleanup of the workspace after successful task completion."""
    logger.info("Performing full workspace cleanup...")
    stash(repo_dir)

    try:
        default_branch = get_default_branch(repo_dir)
        checkout(repo_dir, default_branch, force=True)
    except VLooperError:
        logger.warning("Could not checkout main during cleanup. Detaching HEAD.")
        _, err = run_command(["git", "checkout", "--detach"], cwd=repo_dir)
        if err:
            logger.error("Failed to detach HEAD in cleanup: %s", err)

    reset_hard(repo_dir)
    clean_files(repo_dir)
    delete_branch(repo_dir, branch_name)


def quick_reset(repo_dir):
    """Lighter reset for error handling (stash and switch to main)."""
    logger.info("Performing quick workspace reset...")
    stash(repo_dir)
    try:
        default_branch = get_default_branch(repo_dir)
        checkout(repo_dir, default_branch, force=True)
    except VLooperError as e:
        logger.warning("Quick reset failed (could not checkout main): %s", e)
