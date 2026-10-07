"""Module for managing git operations like repo cloning, branch setup, and committing."""

import os

from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.logger import get_logger
from vlooper.utils import run_command

logger = get_logger(__name__)


def prepare_repo_dir(repo_full_name, repo_short_name):
    """Prepare the repo directory by cloning and resetting to default branch."""
    base_dir = os.path.expanduser(config.workspace_base_dir)
    logger.debug(f"Preparing workspace in: {base_dir}")
    os.makedirs(base_dir, exist_ok=True)
    repo_dir = os.path.join(base_dir, repo_short_name)

    if not os.path.exists(repo_dir):
        logger.info(f"📦 Cloning repository {repo_full_name}...")
        logger.debug(
            f"Clone command: ['gh', 'repo', 'clone', '{repo_full_name}', '{repo_short_name}']"
        )
        _, err = run_command(
            ["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir
        )
        if err:
            raise VLooperError(err)

    logger.info("🧹 Resetting to default branch...")
    base_branch = "main"
    for b in ["main", "master"]:
        logger.debug(f"Checking if '{b}' is a valid base branch...")
        _, err = run_command(["git", "rev-parse", "--verify", b], cwd=repo_dir)
        if not err:
            base_branch = b
            logger.debug(f"Found valid base branch: {base_branch}")
            break

    logger.debug(f"Checking out and pulling {base_branch}...")
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
        logger.warning(f"⚠️ Could not pull origin {base_branch}, proceeding anyway.")
    return repo_dir


def setup_branch(repo_dir, branch_name, task_type):
    """Sets up a new git branch for the given task type."""
    logger.info(f"🌿 Preparing branch {branch_name}...")
    logger.debug(f"Executing: git checkout -B {branch_name}")
    _, err = run_command(
        ["git", "checkout", "-B", branch_name],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        raise VLooperError(err)

    if task_type == "PR":
        logger.info(f"📥 Pulling remote branch {branch_name}...")
        logger.debug(f"Executing: git pull origin {branch_name}")
        _, err = run_command(
            ["git", "pull", "origin", branch_name],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)
    return True


def commit_and_push(repo_dir, branch_name, commit_msg):
    """Commits changes and pushes the branch to origin."""
    logger.info("💾 Committing changes...")
    logger.debug(f"Commit message: {commit_msg}")
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
    logger.debug(f"Executing commit command: {' '.join(commit_cmd)}")
    _, err = run_command(commit_cmd, cwd=repo_dir, timeout=config.execution_timeout)
    if err:
        raise VLooperError(err)

    logger.info("📤 Pushing to origin...")
    push_cmd = ["git", "push", "origin", branch_name]
    logger.debug(f"Executing push command: {' '.join(push_cmd)}")
    _, err = run_command(push_cmd, cwd=repo_dir, timeout=config.execution_timeout)
    if err:
        raise VLooperError(err)
    return True


def stash_and_checkout_main(repo_dir):
    """Stash changes and checkout default branch if a push or PR creation fails."""
    logger.info("🧹 Stashing changes and checking out default branch...")
    run_command(["git", "stash"], cwd=repo_dir)
    base_branch = "main"
    for b in ["main", "master"]:
        _, err = run_command(["git", "checkout", "-f", b], cwd=repo_dir)
        if not err:
            base_branch = b
            break

    logger.debug(f"Checking out {base_branch} after stash...")
    _, err = run_command(
        ["git", "checkout", "-f", base_branch],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        logger.warning(f"⚠️ Failed to checkout default branch during cleanup: {err}")


def delete_local_branch(repo_dir, branch_name):
    """Delete the local git branch after work is done."""
    logger.info(f"🗑 Deleting local branch {branch_name}...")
    # 1. Forcefully clean up any uncommitted changes
    # or untracked files to allow switching branches.
    logger.debug("Running git reset --hard HEAD")
    run_command(["git", "reset", "--hard", "HEAD"], cwd=repo_dir)
    logger.debug("Running git clean -fd")
    run_command(["git", "clean", "-fd"], cwd=repo_dir)

    # 2. Switch back to a default branch (main or master).
    switched = False
    for b in ["main", "master"]:
        logger.debug(f"Attempting to switch back to {b} before deleting branch...")
        _, err = run_command(["git", "checkout", "-f", b], cwd=repo_dir)
        if not err:
            switched = True
            break

    if not switched:
        logger.warning(
            "⚠️ Could not checkout main/master, attempting to detach HEAD..."
        )
        _, err = run_command(["git", "checkout", "--detach"], cwd=repo_dir)
        if not err:
            switched = True

    # 3. Delete the branch.
    logger.debug(f"Deleting local branch {branch_name} via git branch -D")
    _, err = run_command(["git", "branch", "-D", branch_name], cwd=repo_dir)
    if err:
        logger.info(f"ℹ️ Note: Could not delete local branch {branch_name}: {err}")


def delete_remote_branch(repo_dir, branch_name):
    """Attempt to delete the remote git branch."""
    logger.info(f"🗑 Attempting to delete remote branch {branch_name}...")
    logger.debug(f"Executing: git push origin --delete {branch_name}")
    _, err = run_command(
        ["git", "push", "origin", "--delete", branch_name], cwd=repo_dir
    )
    if err:
        logger.info(f"ℹ️ Note: Could not delete remote branch {branch_name}: {err}")
