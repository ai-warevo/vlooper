"""Git CLI client for vLooper operations. Purely executes git commands."""

import os

from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import run_command


logger = get_logger(__name__)


def checkout(repo_dir, branch, force=False):
    """Check out a specific branch."""
    cmd = ["git", "checkout"]
    if force:
        cmd.append("-f")
    cmd.append(branch)
    logger.debug("Executing: %s in %s", " ".join(cmd), repo_dir)
    _, err = run_command(cmd, cwd=repo_dir, timeout=config.timeouts.execution_timeout)
    if err:
        raise VLooperError(f"Git checkout failed: {err}")
    return True


def pull(repo_dir, remote="origin", branch=None, rebase=False):
    """Pull changes from a remote."""
    cmd = ["git", "pull"]
    if rebase:
        cmd.append("--rebase")
    if remote:
        cmd.append(remote)
    if branch:
        cmd.append(branch)

    logger.debug("Executing: %s in %s", " ".join(cmd), repo_dir)
    _, err = run_command(cmd, cwd=repo_dir, timeout=config.timeouts.execution_timeout)
    if err:
        return False, err
    return True, None


def commit(repo_dir, commit_msg):
    """Commit changes with configured user info."""
    logger.info("💾 Committing changes...")
    commit_cmd = [
        "git",
        "-c", f"user.name={config.git.git_user_name}",
        "-c", f"user.email={config.git.git_user_email}",
        "commit",
        "-am",
        commit_msg,
    ]
    _, err = run_command(commit_cmd, cwd=repo_dir, timeout=config.timeouts.execution_timeout)
    if err:
        raise VLooperError(f"Git commit failed: {err}")
    return True


def push(repo_dir, branch, force_with_lease=True):
    """Push changes to remote."""
    cmd = ["git", "push", "origin", branch]
    if force_with_lease:
        cmd.append("--force-with-lease")

    logger.info("📤 Pushing %s to origin...", branch)
    _, err = run_command(cmd, cwd=repo_dir, timeout=config.timeouts.execution_timeout)
    if err:
        raise VLooperError(f"Git push failed: {err}")
    return True


def get_default_branch(repo_dir):
    """Identify the default branch (main or master)."""
    for b in ["main", "master"]:
        # Check if branch exists locally/remotely
        _, err = run_command(["git", "rev-parse", "--verify", b], cwd=repo_dir)
        if not err:
            return b
    raise VLooperError("Could not determine default branch (main or master).")


def reset_hard(repo_dir):
    """Hard reset to HEAD."""
    _, err = run_command(["git", "reset", "--hard", "HEAD"], cwd=repo_dir)
    if err:
        raise VLooperError(f"Git reset hard failed: {err}")


def clean_files(repo_dir):
    """Clean untracked files."""
    _, err = run_command(["git", "clean", "-fd"], cwd=repo_dir)
    if err:
        raise VLooperError(f"Git clean failed: {err}")


def delete_branch(repo_dir, branch_name):
    """Force delete a local branch."""
    _, err = run_command(["git", "branch", "-D", branch_name], cwd=repo_dir)
    if err:
        logger.warning("Could not delete local branch %s: %s", branch_name, err)


def stash(repo_dir):
    """Stash current changes."""
    _, err = run_command(["git", "stash"], cwd=repo_dir)
    if err:
        raise VLooperError(f"Git stash failed: {err}")


def is_remote_branch_exists(repo_dir, branch_name):
    """Check if a branch exists on origin."""
    cmd = ["git", "ls-remote", "--heads", "origin", branch_name]
    stdout, err = run_command(cmd, cwd=repo_dir)
    if err:
        return False
    return stdout and branch_name in stdout
