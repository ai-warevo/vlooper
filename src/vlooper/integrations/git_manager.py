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


def commit_and_push(repo_dir, branch_name, commit_msg):
    """Commits changes and pushes the branch to origin."""
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

    logger.info("📤 Pushing to origin...")
    push_cmd = ["git", "push", "origin", branch_name]
    logger.debug("Executing push command: %s", " ".join(push_cmd))
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

    logger.debug("Checking out %s after stash...", base_branch)
    _, err = run_command(
        ["git", "checkout", "-f", base_branch],
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        logger.warning("⚠️ Failed to checkout default branch during cleanup: %s", err)


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
    switched = False
    for b in ["main", "master"]:
        logger.debug("Attempting to switch back to %s before deleting branch...", b)
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
    logger.debug("Deleting local branch %s via git branch -D", branch_name)
    _, err = run_command(["git", "branch", "-D", branch_name], cwd=repo_dir)
    if err:
        logger.info("ℹ️ Note: Could not delete local branch %s: %s", branch_name, err)


def delete_remote_branch(repo_dir, branch_name):
    """Attempt to delete the remote git branch."""
    logger.info("🗑 Attempting to delete remote branch %s...", branch_name)
    logger.debug("Executing: git push origin --delete %s", branch_name)
    _, err = run_command(
        ["git", "push", "origin", "--delete", branch_name], cwd=repo_dir
    )
    if err:
        logger.info("ℹ️ Note: Could not delete remote branch %s: %s", branch_name, err)


def filter_ignored_lines(repo_dir: str, text: str) -> str:
    """Filter out lines from the text that are in .gitignore."""
    if not text.strip():
        return text

    lines = text.splitlines()
    input_text = "\n".join(lines)

    try:
        cmd = ["git", "check-ignore", "--stdin"]
        stdout, err = run_command(cmd, cwd=repo_dir, input=input_text)

        if err:
            return text

        ignored_paths = set(stdout.splitlines())

        filtered_lines = [
            line for line in lines
            if line.strip() not in ignored_paths and line.strip() != ""
        ]

        return "\n".join(filtered_lines)
    except Exception as e:
        logger.warning("Failed to filter ignored lines via git: %s", e)
        return text

