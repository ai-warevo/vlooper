"""Scanner module to find issues and PRs using GitHub CLI."""

import json

from vlooper.config import config
from vlooper.database import Database
from vlooper.utils import build_gh_view_cmd, run_command


class Scanner:  # pylint: disable=too-few-public-methods
    """Scanner to find issues and Pull Requests assigned to the bot."""

    def __init__(self, db: Database):
        """Initialize the scanner with a database instance."""
        self.db = db

    def scan(self, retry_failed=False):
        """Perform periodic scanning of organization for new tasks."""
        if retry_failed:
            print("🔄 Mode: Retrying stale failed tasks (5m cooldown)...")
            self._retry_failed_tasks()

        print(f"🔍 Scanning for new tasks in organization: {config.org_name}...")
        self._scan_issues()
        self._scan_prs()

    def _retry_failed_tasks(self):
        """Retrieve stale failed tasks from DB and reset them."""
        # 300 seconds = 5 minutes cooldown to prevent rapid retry loops for failing tasks.
        failed_tasks = self.db.get_failed_tasks(min_age_seconds=300)
        if not failed_tasks:
            return

        print(f"♻️ Found {len(failed_tasks)} stale failed tasks. Resetting them...")
        for task in failed_tasks:
            self.db.reset_task_status(task["id"])
            print(f"   ✅ Task #{task['id']} reset to PENDING.")

    def _scan_issues(self):
        """Scan for open issues assigned to the bot."""
        search_issues_cmd = [
            "gh",
            "search",
            "issues",
            f"org:{config.org_name}",
            f"assignee:{config.bot_username}",
            "state:open",
            "is:issue",
            "--json",
            "number,title,body,repository,isPullRequest",
        ]
        issues_json, err = run_command(search_issues_cmd)
        if err or not issues_json:
            return

        try:
            issues = json.loads(issues_json)
        except json.JSONDecodeError:
            print("Failed to parse issues JSON.")
            return

        for issue in issues:
            if issue.get("isPullRequest"):
                continue

            num = issue["number"]
            repo_full_name = issue["repository"]["nameWithOwner"]
            # For issues, we might want a representative branch name or just use 'issue-{num}'
            branch_name = f"issue-{num}"
            self.db.add_task("ISSUE", repo_full_name, branch_name)

    def _scan_prs(self):
        """Scan for open Pull Requests assigned to the bot."""
        search_prs_cmd = [
            "gh",
            "search",
            "issues",
            f"org:{config.org_name}",
            f"assignee:{config.bot_username}",
            "state:open",
            "is:pr",
            "--json",
            "number,title,body,repository,isPullRequest",
        ]
        prs_json, err = run_command(search_prs_cmd)
        if err or not prs_json:
            return

        try:
            prs = json.loads(prs_json)
        except json.JSONDecodeError:
            print("Failed to parse PRs JSON.")
            return

        for pr in prs:
            if not pr.get("isPullRequest"):
                continue

            num = pr["number"]
            repo_full_name = pr["repository"]["nameWithOwner"]

            # Get the branch name for the PR
            pr_details_cmd = build_gh_view_cmd(
                "pr", num, repo_full_name, ["headRefName"]
            )
            pr_details_json, err = run_command(pr_details_cmd)
            if err or not pr_details_json:
                continue

            try:
                pr_data = json.loads(pr_details_json)
                branch = pr_data.get("headRefName")
                if branch:
                    self.db.add_task("PR", repo_full_name, branch)
            except (json.JSONDecodeError, KeyError):
                print(f"Failed to parse PR details for #{num}")
