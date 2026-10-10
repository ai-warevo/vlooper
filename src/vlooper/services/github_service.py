"""Module for interacting with GitHub via CLI (gh)."""

from vlooper.clients.github_client import (
    clone_repository,
    create_pull_request,
    get_issue_author,
    get_item_info,
    post_comment,
    search_issues,
)
from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


def create_pull_request_workflow(repo_full_name, title, body, cwd):
    """Wrapper for GitHub CLI pull request creation. Returns structured details."""
    res, err = create_pull_request(
        repo_full_name=repo_full_name, title=title, body=body, cwd=cwd
    )
    if err:
        return None, err
    return {"html_url": res.strip()}, None


def clone_repository_workflow(repo_full_name, repo_short_name, base_dir):
    """Wrapper for GitHub CLI repository cloning."""
    success, err = clone_repository(
        repo_full_name=repo_full_name,
        repo_short_name=repo_short_name,
        base_dir=base_dir,
    )
    if not success:
        return False, err
    return True, None


def post_github_comment(task, message):
    """Helper to post a comment to the respective GitHub issue or PR."""
    repo_full_name = task["repo_full_name"]
    task_type = task["task_type"]
    branch_name = task.get("branch_name")
    issue_num = task.get("issue_number")

    if task_type == "ISSUE":
        try:
            # Try to get number from branch name if available
            num = None
            if branch_name:
                parts = branch_name.split("-")
                if len(parts) >= 2:
                    num = parts[-1]

            # Fallback to issue_number from task dict
            if not num and issue_num:
                num = str(issue_num)

            if num:
                _, err = post_comment(repo_full_name, num, message)
                if err:
                    logger.warning(
                        "Failed to post GitHub comment for #%s: %s", num, err
                    )
            else:
                logger.warning(
                    "Could not find issue number in branch name or task data: %s (branch: %s)",
                    issue_num,
                    branch_name,
                )
        except Exception as e:  # noqa: W0718
            logger.error("Error posting GitHub comment: %s", e)
    elif task_type == "PR":
        logger.debug(get_pr_details(repo_full_name, branch_name))
        logger.debug("TODO: pr comment logic ...")


def get_github_author(task):
    """Fetch the author of the issue/PR to mention them."""
    repo_full_name = task["repo_full_name"]
    if task["task_type"] == "ISSUE":
        num = get_issue_number(task)
        if num != "unknown" and num:
            author = get_issue_author(repo_full_name, num)
            if author:
                return author
    return "assignee"


def get_issue_number(task):
    """Get issue number from task."""
    if task["task_type"] == "ISSUE":
        try:
            # Try branch name first
            if task.get("branch_name"):
                return task["branch_name"].split("-")[-1]
            # Fallback to issue_number field
            if task.get("issue_number"):
                return str(task["issue_number"])
        except Exception:
            logger.debug("Failed to parse issue number from branch name.")
        return "unknown"
    return "PR"


def get_assigned_items(org_name, bot_username, is_pr=False):
    """Service method to fetch assigned items."""
    return search_issues(org_name=org_name, bot_username=bot_username, is_pr=is_pr)


def get_github_item(num, repo_full_name, item_type="issue", fields=None):
    """Service method to fetch a specific GitHub item."""
    if fields is None:
        fields = "title,body"
    return get_item_info(num, repo_full_name, item_type, fields)
