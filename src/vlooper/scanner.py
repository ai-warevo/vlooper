import json
import subprocess

from vlooper.config import config
from vlooper.database import Database


def run_command(cmd):
    """Helper to run shell commands."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}\nError: {res.stderr}")
        return None
    return res.stdout.strip()


class Scanner:
    def __init__(self, db: Database):
        self.db = db

    def scan(self):
        print(f"🔍 Scanning for new tasks in organization: {config.org_name}...")
        self._scan_issues()
        self._scan_prs()

    def _scan_issues(self):
        search_issues_cmd = [
            "gh",
            "search",
            "issues",
            f"org:{config.org_name}",
            f"assignee:{config.bot_username}",
            "state:open",
            "type:issue",
            "--json",
            "number,title,body,repository",
        ]
        issues_json = run_command(search_issues_cmd)
        if not issues_json:
            return

        try:
            issues = json.loads(issues_json)
        except json.JSONDecodeError:
            print("Failed to parse issues JSON.")
            return

        for issue in issues:
            num = issue["number"]
            repo_full_name = issue["repository"]["nameWithOwner"]
            # For issues, we might want a representative branch name or just use 'issue-{num}'
            branch_name = f"issue-{num}"
            self.db.add_task("ISSUE", repo_full_name, branch_name)

    def _scan_prs(self):
        search_prs_cmd = [
            "gh",
            "search",
            "issues",
            f"org:{config.org_name}",
            f"assignee:{config.bot_username}",
            "state:open",
            "type:pr",
            "--json",
            "number,title,body,repository",
        ]
        prs_json = run_command(search_prs_cmd)
        if not prs_json:
            return

        try:
            prs = json.loads(prs_json)
        except json.JSONDecodeError:
            print("Failed to parse PRs JSON.")
            return

        for pr in prs:
            num = pr["number"]
            repo_full_name = pr["repository"]["nameWithOwner"]

            # Get the branch name for the PR
            pr_details_cmd = [
                "gh",
                "pr",
                "view",
                str(num),
                "--repo",
                repo_full_name,
                "--json",
                "headRefName",
            ]
            pr_details_json = run_command(pr_details_cmd)
            if not pr_details_json:
                continue

            try:
                pr_data = json.loads(pr_details_json)
                branch = pr_data.get("headRefName")
                if branch:
                    self.db.add_task("PR", repo_full_name, branch)
            except (json.JSONDecodeError, KeyError):
                print(f"Failed to parse PR details for #{num}")
