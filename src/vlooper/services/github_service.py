"""Module for interacting with GitHub via CLI (gh)."""

from vlooper.config import config
from vlooper.core.exceptions import VLooperError
from vlooper.clients.github_client import (
    clone_repository,
    create_pull_request,
    get_issue_details,
    get_pr_details,
)
from vlooper.logger import get_logger
from vlooper.utils import build_gh_view_cmd, run_command


logger = get_logger(__name__)


def create_pull_request_workflow(repo_full_name, title, body, cwd):
    """Wrapper for GitHub CLI pull request creation. Returns structured details."""
    res, err = create_pull_request(
        repo_full_name=repo_full_name,
        title=title,
        body=body,
        cwd=cwd
    )
    if err:
        return None, err
    return {"html_url": res.strip()}, None


def clone_repository_workflow(repo_full_name, repo_short_name, base_dir):
    """Wrapper for GitHub CLI repository cloning."""
    success, err = clone_repository(
        repo_full_name=repo_full_name,
        repo_short_name=repo_short_name,
        base_dir=base_dir
    )
    if not success:
        return False, err
    return True, None


def post_github_comment(task, message):
    """Helper to post a comment to the respective GitHub issue or PR."""
    repo_full_name = task["repo_full_name"]
    task_type = task["task_type"]
    branch_name = task["branch_name"]

    if task_type == "ISSUE":
        try:
            # Extracting number from branch name like 'issue-123'
            parts = branch_name.split("-")
            if len(parts) >= 2:
                num = parts[-1]
                comment_cmd = [
                    "gh",
                    "issue",
                    "comment",
                    str(num),
                    "--repo",
                    repo_full_name,
                    "--body",
                    message,
                ]
                _, err = run_command(comment_cmd)
                if err:
                    logger.warning(
                        "Failed to post GitHub comment for #%s: %s", num, err
                    )
            else:
                logger.warning(
                    "Could not find issue number in branch name: %s", branch_name
                )
        except Exception as e:  # noqa: W0718
            logger.error("Error posting GitHub comment: %s", e)
    elif task_type == "PR":
        logger.debug("TODO: pr comment logic ...")
        # For PRs, this is handled by different logic or requires more state.


def get_github_author(task):
    """Fetch the author of the issue/PR to mention them."""
    repo_full_name = task["repo_full_name"]
    if task["task_type"] == "ISSUE":
        num = get_issue_number(task)
        if num != "unknown" and num:
            cmd = build_gh_view_cmd(
                "issue", num, repo_full_name, ["author", "--jq", ".author.login"]
            )
            stdout, err = run_command(cmd)
            if not err and stdout:
                return stdout
    return "assignee"


def get_issue_number(task):
    """Get issue number from task."""
    if task["task_type"] == "ISSUE":
        try:
            return task["branch_name"].split("-")[-1]
        except Exception:  # noqa: W0718
            return "unknown"
    return "PR"
