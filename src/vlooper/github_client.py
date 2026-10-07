"""GitHub CLI client for vLooper operations."""

import json

from vlooper.utils import run_command
from vlooper.i18n import i18n


def get_issue_info(num, repo_full_name, fields="title,body"):
    """Fetch issue information with specified JSON fields via GitHub CLI."""
    cmd = ["gh", "issue", "view", str(num), "--repo", repo_full_name, "--json", fields]
    res, err = run_command(cmd)
    if err or not res:
        return None
    try:
        return json.loads(res)
    except (json.JSONDecodeError, KeyError):
        return None


def get_issue_details(num, repo_full_name, bot_username=None):
    """Fetch issue details including title, body and comments."""
    data = get_issue_info(num, repo_full_name, "title,body")
    if not data:
        return None

    title = data.get("title")
    body = data.get("body") or ""

    comments_data = get_issue_info(num, repo_full_name, "comments")
    comments_text = ""
    bot_has_replied = False
    if comments_data and "comments" in comments_data:
        try:
            comments_list = comments_data["comments"]
            lines = []
            for c in comments_list:
                author = c['author']['login']
                body_text = c['body'] or ""
                if bot_username and author == bot_username:
                    bot_has_replied = True
                msg = i18n.t("github.comment_header", author=author, body=body_text)
                lines.append(msg)
            comments_text = "\n".join(lines)
        except (KeyError, TypeError):
            pass

    return title, body, comments_text, bot_has_replied


def get_pr_details(repo_full_name, branch, bot_username=None):
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

        bot_has_replied = False
        review_text = ""
        for r in pr.get("reviews", []):
            if r.get("body"):
                author = r['author']['login']
                if bot_username and author == bot_username:
                    bot_has_replied = True
                review_text += i18n.t("github.review_header", author=author, body=r['body'])
        for c in pr.get("comments", []):
            author = c['author']['login']
            if bot_username and author == bot_username:
                bot_has_replied = True
            review_text += i18n.t("github.remark_header", author=author, body=c['body'])

        return num, title, body, review_text, bot_has_replied
    except (json.JSONDecodeError, KeyError):
        return None


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
