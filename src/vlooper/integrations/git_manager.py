"""Module for managing git operations like repo cloning, branch setup, and committing."""

import os

from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.logger import get_logger
from vlooper.utils import run_command

logger = get_logger(__name__)


def prepare_repo_dir(repo_full_name, repo_short_name, skip_reset=False):
    """Prepare the repo directory by cloning and optionally resetting to default branch."""
    base_dir = os.path.expanduser(config.workspace_base_dir)
    logger.debug("Preparing workspace in: %s", base_dir)
    os.makedirs(base_dir, exist_ok=True)
    repo_dir = os.path.join(base_dir, repo_short_name)

    if not os.path.exists(repo_dir):
        logger.info("📦 Cloning repository %s...", repo_full_name)
        logger.debug(
            "Clone command: ['gh', 'repo', 'clone', '%s', '%s']",
            repo_full_name,
            repo_short_name,
        )
        _, err = run_command(
            ["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir
        )
        if err:
            raise VLooperError(err)

    if skip_reset:
        logger.info("⏩ Skipping destructive reset to main (preserving current workspace state).")
        return repo_dir

    logger.info("🧹 Resetting to default branch...")
    base_branch = "main"
    for b in ["main", "master"]:
        logger.debug("Checking if '%s' is a valid base branch...", b)
        _, err = run_command(["git", "rev-parse", "--verify", b], cwd=repo_dir)
        if not err:
            base_branch = b
            logger.debug("Found valid base branch: %s", base_branch)
            break

    logger.debug("Checking out and pulling %s...", base_branch)
    _, err = run_command(
        ["git", "checkout", "-f", base_branch],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        raise VLooperError(err)

    _, err = run_command(
        ["git", "pull", "origin", base_branch],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        logger.warning("⚠️ Could not pull origin %s, proceeding anyway.", base_branch)
    return repo_dir


def setup_branch(repo_dir, branch_name, task_type):
    """Sets up a new git branch for the given task type."""
    logger.info("🌿 Preparing branch %s...", branch_name)
    logger.debug("Executing: git checkout -B %s", branch_name)
    _, err = run_command(
        ["git", "checkout", "-B", branch_name],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        raise VLooperError(err)

    if task_type == "PR":
        logger.info("📥 Pulling remote branch %s...", branch_name)
        logger.debug("Executing: git pull origin %s", branch_name)
        _, err = run_command(
            ["git", "pull", "origin", branch_name],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)
    return True


def commit(repo_dir, commit_msg):
    """Commits changes."""
    logger.info("💾 Committing changes...")
    logger.debug("Commit message: %s", commit_msg)
    commit_cmd = [
        "git",
        "-c",
        f"user.name={config.git_user_name}",
        "-c",
        f"user.email={config.git_user_email}",
        "commit",
        "-am",
        commit_msg,
    ]
    logger.debug("Executing commit command: %s", " ".join(commit_cmd))
    _, err = run_command(commit_cmd, cwd=repo_dir, timeout=config.execution_timeout)
    if err:
        raise VLooperError(err)
    return True


def push(repo_dir, branch_name):
    """Pushes the branch to origin using a smart rebase strategy."""
    # SMART STEP: Check if the branch already exists on remote before rebasing
    logger.info("🔍 Checking if remote branch '%s' exists...", branch_name)
    check_remote_cmd = ["git", "ls-remote", "--heads", "origin", branch_name]
    stdout, err = run_command(check_remote_cmd, cwd=repo_dir)

    # If stdout is not empty and contains the branch name, it exists on remote
    if stdout and branch_name in stdout:
        logger.info("🔄 Remote branch found. Attempting rebase to synchronize history...")
        rebase_cmd = ["git", "pull", "--rebase", "origin", branch_name]
        logger.debug("Executing rebase command: %s", " ".join(rebase_cmd))
        _, err = run_command(rebase_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err:
            logger.error("❌ Rebase failed. This usually means there are merge conflicts.")
            raise VLooperError(f"Rebase failed/conflict detected: {err}")
    else:
        logger.info("ℹ️ Remote branch not found (this is likely the first push). Skipping rebase.")

    logger.info("📤 Pushing to origin...")
    # Use force-with-lease as a safety measure after rebase or for new branches
    push_cmd = ["git", "push", "origin", branch_name, "--force-with-lease"]
    logger.debug("Executing push command: %s", " ".join(push_cmd))
    _, err = run_command(push_cmd, cwd=repo_dir, timeout=config.execution_timeout)
    if err:
        raise VLooperError(err)
    return True


def commit_and_push(repo_dir, branch_name, commit_msg):
    """Commits changes and pushes the branch to origin using a smart rebase strategy."""
    commit(repo_dir, commit_msg)
    push(repo_dir, branch_name)
    return True


def checkout_default_branch(repo_dir):
    """Attempts to check out one of the default branches (main or master)."""
    for b in ["main", "master"]:
        logger.debug("Attempting to checkout %s...", b)
        _, err = run_command(["git", "checkout", "-f", b], cwd=repo_dir, timeout=config.execution_timeout)
        if not err:
            return b
    raise VLooperError("Could not find or checkout a default branch (main/master).")


def stash_and_checkout_main(repo_dir):
    """Stash changes and checkout default branch if a push or PR creation fails."""
    logger.info("🧹 Stashing changes and checking out default branch...")
    run_command(["git", "stash"], cwd=repo_dir)
    try:
        checkout_default_branch(repo_dir)
    except VLooperError as e:
        logger.warning("⚠️ Failed to checkout default branch during cleanup: %s", e)


def delete_local_branch(repo_dir, branch_name):
    """Delete the local git branch after work is done."""
    logger.info("🗑 Deleting local branch %s...", branch_name)
    # 1. Forcefully clean up any uncommitted changes
    # or untracked files to allow switching branches.
    logger.debug("Running git reset --hard HEAD")
    run_command(["git", "reset", "--hard", "HEAD"], cwd=repo_dir)
    logger.debug("Running git clean -fd")
    run_command(["git", "clean", "-fd"], cwd=repo_dir)

    # 2. Switch back to a default branch (main or master).
    try:
        checkout_default_branch(repo_dir)
    except VLooperError:
        logger.warning("⚠️ Could not checkout main/master, attempting to detach HEAD...")
        _, err = run_command(["git", "checkout", "--detach"], cwd=repo_dir)
        if err:
            logger.error("❌ Failed to detach HEAD: %s", err)

    # 3. Delete the branch.
    logger.debug("Deleting local branch %s via git branch -D", branch_name)
    _, err = run_command(["git", "branch", "-D", branch_name], cwd=repo_dir)
    if err:
        logger.info("ℹ️ Note: Could not delete local branch %s: %s", branch_name, err)
