"""GitHub CLI client for vLooper operations."""
import json

from vlooper.utils import run_command


def get_issue_details(num, repo_full_name):
    """Fetch issue details including title, body and comments."""
    view_cmd = [
        "gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", "title,body",
    ]
    res, err = run_command(view_cmd)
    if err or not res:
        return None

    try:
        issue_data = json.loads(res)
        title = issue_data["title"]
        body = issue_data["body"] or ""

        comments_cmd = [
            "gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", "comments",
        ]
        res_c, err_c = run_command(comments_cmd)
        comments_text = ""
        if not err_c and res_c:
            comments = json.loads(res_c).get("comments", [])
            comments_text = "\n".join(
                [f"Комментарий от {c['author']['login']}: {c['body']}" for c in comments]
            )

        return title, body, comments_text
    except (json.JSONDecodeError, KeyError):
        return None


def get_pr_details(repo_full_name, branch):
    """Fetch PR details including reviews and comments."""
    list_pr_cmd = [
        "gh", "pr", "list", "--repo", repo_full_name, "--head", branch,
        "--json", "number,title,body,comments,reviews",
    ]
    res_p, err_p = run_command(list_pr_cmd)
    if err_p or not res_p:
        return None

    try:
        prs = json.loads(res_p)
        if not prs:
            return None
        pr = prs[0]
        num = pr["number"]
        title = pr["title"]
        body = pr["body"] or ""

        review_text = ""
        for r in pr.get("reviews", []):
            if r.get("body"):
                review_text += f"Ревью от {r['author']['login']}: {r['body']}\n"
        for c in pr.get("comments", []):
            review_text += f"Замечание от {c['author']['login']}: {c['body']}\n"

        return num, title, body, review_text
    except (json.JSONDecodeError, KeyError):
        return None


def create_pull_request(repo_full_name, title, body):
    """Create a pull request using GitHub CLI."""
    pr_create_cmd = [
        "gh", "pr", "create", "--repo", repo_full_name, "--title", title, "--body", body,
    ]
    return run_command(pr_create_cmd)
