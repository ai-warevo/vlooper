"""Module for interacting with GitHub via CLI (gh)."""

from vlooper.config import config
from vlooper.utils import build_gh_view_cmd, run_command
from vlooper.github_client import create_pull_request, get_issue_details, get_pr_details
from vlooper.exceptions import VLooperError


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
                    print(f"⚠️ Failed to post GitHub comment for #{num}: {err}")
            else:
                print(f"⚠️ Could not find issue number in branch name: {branch_name}")
        except Exception as e:  # noqa: W0718
            print(f"⚠️ Error posting GitHub comment: {e}")
    elif task_type == "PR":
        # For PRs, this is handled by different logic or requires more state.
        pass


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


def create_pr(repo_full_name, repo_dir, branch_name):
    """Creates a Pull Request."""
    print("📢 Creating Pull Request...")
    _, err = create_pull_request(
        repo_full_name,
        f"Fix for {branch_name}",
        "Automated fix by vLooper agent.",
        cwd=repo_dir,
        timeout=config.execution_timeout,
    )
    if err:
        raise VLooperError(err)

    details = get_pr_details(repo_full_name, branch_name)
    if details:
        return details[0]
    return None


def get_issue_context(task, repo_full_name):
    """Fetch context for the task from GitHub."""
    num = (
        task["branch_name"].split("-")[-1] if "-" in task["branch_name"] else "unknown"
    )
    if num == "unknown":
        return None

    details = get_issue_details(num, repo_full_name)
    if not details:
        return None
    title, body, comments_text = details

    return (
        f"Задача #{num} в репозитории {repo_full_name}: {title}\n"
        f"Описание:\n{body}\n\nИстория переписки:\n{comments_text}"
    )


def get_pr_context(task, repo_full_name):
    """Fetch context for the task from a Pull Request on GitHub."""
    try:
        details = get_pr_details(repo_full_name, task["branch_name"])
        if not details:
            return None

        num, _, body, review_text = details

        if "Исправлено ботом" in review_text:
            return None

        return (
            f"Доработка по Pull Request #{num} в репозитории "
            f"{repo_full_name} (ветка {task['branch_name']}).\nЗамечания к коду:\n"
            f"{review_text}\n\nОписание PR:\n{body}"
        )
    except Exception:  # noqa: W0718
        return None


def get_issue_number(task):
    """Get issue number from task."""
    if task["task_type"] == "ISSUE":
        try:
            return task["branch_name"].split("-")[-1]
        except Exception:  # noqa: W0718
            return "unknown"
    return "PR"


def get_pr_details_wrapper(repo_full_name, branch_name):
    """Wrapper for getting PR details."""
    return get_pr_details(repo_full_name, branch_name)
