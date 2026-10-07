"""Scanner module to find issues and PRs using GitHub CLI."""

import json

from vlooper.config import config
from vlooper.database import Database
from vlooper.logger import get_logger
from vlooper.utils import build_gh_view_cmd, run_command

logger = get_logger(__name__)


class Scanner:  # pylint: disable=too-few-public-methods
    """Scanner to find issues and Pull Requests assigned to the bot."""

    def __init__(self, db: Database):
        """Initialize the scanner with a database instance."""
        self.db = db

    def scan(self, retry_failed=False):
        """Perform periodic scanning of organization for new tasks."""
        if retry_failed:
            logger.info("🔄 Mode: Retrying stale failed tasks (5m cooldown)...")
            self._retry_failed_tasks()

        logger.info("🔍 Scanning for new tasks in organization: %s...", config.org_name)
        self._scan_issues()
        self._scan_prs()

    def _retry_failed_tasks(self):
        """Retrieve stale failed tasks from DB and reset them."""
        # cooldown to prevent rapid retry loops for failing tasks.
        failed_tasks = self.db.get_failed_tasks(
            min_age_seconds=config.failed_task_cooldown_seconds
        )
        if not failed_tasks:
            logger.debug("No stale failed tasks found to retry.")
            return

        logger.info(
            "♻️ Found %s stale failed tasks. Resetting them...", len(failed_tasks)
        )
        for task in failed_tasks:
            logger.debug("Resetting task #%s to PENDING.", task["id"])
            self.db.reset_task_status(task["id"])
            logger.info("   ✅ Task #%s reset to PENDING.", task["id"])

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
        logger.debug("Running issue search command: %s", " ".join(search_issues_cmd))
        issues_json, err = run_command(search_issues_cmd)
        if err or not issues_json:
            logger.debug("Issue search failed or returned no data. Error: %s", err)
            return

        try:
            issues = json.loads(issues_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse issues JSON.")
            return

        logger.debug(
            "Parsed %s potential issue/PR items from GitHub search.", len(issues)
        )

        for issue in issues:
            if issue.get("isPullRequest"):
                continue

            num = issue["number"]
            repo_full_name = issue["repository"]["nameWithOwner"]
            # For issues, we might want a representative branch name or just use 'issue-{num}'
            branch_name = f"issue-{num}"
            logger.debug(
                "Adding task for issue #%s: %s (branch: %s)",
                num,
                repo_full_name,
                branch_name,
            )
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
        logger.debug("Running PR search command: %s", " ".join(search_prs_cmd))
        prs_json, err = run_command(search_prs_cmd)
        if err or not prs_json:
            logger.debug("PR search failed or returned no data. Error: %s", err)
            return

        try:
            prs = json.loads(prs_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse PRs JSON.")
            return

        logger.debug("Parsed %s potential issue/PR items from GitHub search.", len(prs))

        for pr in prs:
            if not pr.get("isPullRequest"):
                continue

            num = pr["number"]
            repo_full_name = pr["repository"]["nameWithOwner"]

            # Get the branch name for the PR
            logger.debug("Fetching details for PR #%s to get head branch...", num)
            pr_details_cmd = build_gh_view_cmd(
                "pr", num, repo_full_name, ["headRefName"]
            )
            pr_details_json, err = run_command(pr_details_cmd)
            if err or not pr_details_json:
                logger.debug("Could not fetch details for PR #%s. Skipping.", num)
                continue

            try:
                pr_data = json.loads(pr_details_json)
                branch = pr_data.get("headRefName")
                if branch:
                    logger.debug(
                        "Adding task for PR #%s: %s (branch: %s)",
                        num,
                        repo_full_name,
                        branch,
                    )
                    self.db.add_task("PR", repo_full_name, branch)
            except (json.JSONDecodeError, KeyError):
                logger.error("Failed to parse PR details for #%s", num)
