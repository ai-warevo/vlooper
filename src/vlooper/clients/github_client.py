"""GitHub CLI client for vLooper operations."""

import json

from vlooper.infra.utils import run_command


def clone_repository(repo_full_name, repo_short_name, base_dir):
    """Clone a repository using GitHub CLI."""
    print(f"📦 Cloning repository {repo_full_name}...")
    cmd = ["gh", "repo", "clone", repo_full_name, repo_short_name]
    res, err = run_command(cmd, cwd=base_dir)
    if err:
        return False, err
    return True, None


def get_item_info(num, repo_full_name, item_type="issue", fields="title,body"):
    """Fetch issue or PR information with specified JSON fields via GitHub CLI."""
    cmd = ["gh", item_type, "view", str(num), "--repo", repo_full_name, "--json", fields]
    res, err = run_command(cmd)
    if err or not res:
        return None
    try:
        return json.loads(res)
    except (json.JSONDecodeError, KeyError):
        return None


def get_issue_info(num, repo_full_name, fields="title,body"):
    """Fetch issue information with specified JSON fields via GitHub CLI."""
    return get_item_info(num, repo_full_name, "issue", fields)


def get_issue_details(num, repo_full_name):
    """Fetch issue details including title, body and comments."""
...
    """Fetch issue details including title, body and comments."""
    data = get_issue_info(num, repo_full_name, "title,body")
    if not data:
        return None

    title = data.get("title")
    body = data.get("body") or ""

    comments_data = get_issue_info(num, repo_full_name, "comments")
    comments_text = ""
    if comments_data and "comments" in comments_data:
        try:
            comments_list = comments_data["comments"]
            comments_text = "\n".join(
                [
                    f"Comment by {c['author']['login']}: {c['body']}"
                    for c in comments_list
                ]
            )
        except (KeyError, TypeError):
            pass

    return title, body, comments_text


def get_pr_details(repo_full_name, branch):
    """Fetch PR details including reviews and comments."""
    list_pr_cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo_full_name,
        "--head",
        branch,
        "--json",
        "number,title,body,comments,reviews",
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
                review_text += f"Review by {r['author']['login']}: {r['body']}\n"
        for c in pr.get("comments", []):
            review_text += f"Comment by {c['author']['login']}: {c['body']}\n"

        return num, title, body, review_text
    except (json.JSONDecodeError, KeyError):
        return None


def post_comment(repo_full_name, num, message):
    """Post a comment to an issue or PR."""
    cmd = [
        "gh",
        "issue", # works for both issues and prs in gh CLI for commenting
        "comment",
        str(num),
        "--repo",
        repo_full_name,
        "--body",
        message,
    ]
    res, err = run_command(cmd)
    return res, err


def get_issue_author(repo_full_name, num):
    """Get the author of an issue or PR."""
    cmd = [
        "gh",
        "issue",
        "view",
        str(num),
        "--repo",
        repo_full_name,
        "--jq",
        ".author.login",
    ]
    res, err = run_command(cmd)
    if err or not res:
        return None
    return res.strip()


def search_issues(org_name, bot_username, is_pr=False, fields="number,title,body,repository,isPullRequest"):
    """Search for issues or PRs in an organization assigned to a user."""
    filter_type = "is:pr" if is_pr else "is:issue"
    cmd = [
        "gh",
        "search",
        "issues",
        f"org:{org_name}",
        f"assignee:{bot_username}",
        "state:open",
        filter_type,
        "--json",
        fields,
    ]
    res, err = run_command(cmd)
    if err or not res:
        return None, err
    try:
        return json.loads(res), None
    except (json.JSONDecodeError, KeyError):
        return None, "Failed to parse issues JSON"


def create_pull_request(repo_full_name, title, body, cwd=None, timeout=None):
    """Create a pull request using GitHub CLI."""
    pr_create_cmd = [
        "gh",
        "pr",
        "create",
        "--repo",
        repo_full_name,
        "--title",
        title,
        "--body",
        body,
    ]
    return run_command(pr_create_cmd, cwd=cwd, timeout=timeout)
