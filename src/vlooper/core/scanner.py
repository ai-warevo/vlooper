"""Scanner module to find issues and PRs using GitHub CLI."""

import json

from vlooper.infra.config import config
from vlooper.infra.database import Database
from vlooper.infra.logger import get_logger
from vlooper.services.github_service import get_assigned_items, get_github_item

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
        logger.debug("Scanning for issues in organization: %s...", config.org_name)
        issues, err = get_assigned_items(
            org_name=config.org_name,
            bot_username=config.bot_username,
            is_pr=False
        )
        if err:
            logger.debug("Issue search failed. Error: %s", err)
            return
        if not issues:
            logger.debug("No issues found.")
            return

        logger.debug(
            "Found %s potential issue/PR items from GitHub search.", len(issues)
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
            self.db.add_task("ISSUE", repo_full_name, f"https://github.com/{repo_full_name}", num, branch_name)

    def _scan_prs(self):
        """Scan for open Pull Requests assigned to the bot."""
        logger.debug("Scanning for PRs in organization: %s...", config.org_name)
        prs, err = get_assigned_items(
            org_name=config.org_name,
            bot_username=config.bot_username,
            is_pr=True
        )
        if err:
            logger.debug("PR search failed. Error: %s", err)
            return
        if not prs:
            logger.debug("No PRs found.")
            return

        logger.debug(
            "Found %s potential issue/PR items from GitHub search.", len(prs)
        )

        for pr in prs:
            if not pr.get("isPullRequest"):
                continue

            num = pr["number"]
            repo_full_name = pr["repository"]["nameWithOwner"]

            # Get the branch name for the PR
            logger.debug("Fetching details for PR #%s to get head branch...", num)
            pr_data = get_github_item(num, repo_full_name, item_type="pr", fields=["headRefName"])
            if not pr_data:
                logger.debug("Could not fetch details for PR #%s. Skipping.", num)
                continue

            branch = pr_data.get("headRefName")
            if branch:
                logger.debug(
                    "Adding task for PR #%s: %s (branch: %s)",
                    num,
                    repo_full_name,
                    branch,
                )
                self.db.add_task("PR", repo_full_name, f"https://github.com/{repo_full_name}", num, branch)
            else:
                logger.warning("Could not find headRefName for PR #%s.", num)
