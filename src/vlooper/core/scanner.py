"""Scanner module to find issues and PRs using GitHub CLI."""

from typing import Any, Dict, Optional

import json

from vlooper.config import config
from vlooper.persistence.database import Database
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
            logger.info("Mode: Retrying stale failed tasks (5m cooldown)...")
            self._retry_failed_tasks()

        logger.info("Scanning for new tasks in organization: %s...", config.git.org_name)
        self._scan_issues()
        self._scan_prs()

    def _retry_failed_tasks(self):
        """Retrieve stale failed tasks from DB and reset them."""
        # cooldown to prevent rapid retry loops for failing tasks.
        failed_tasks = self.db.get_failed_tasks(
            min_age_seconds=config.timeouts.failed_task_cooldown_seconds
        )
        if not failed_tasks:
            logger.debug("No stale failed tasks found to retry.")
            return

        logger.info(
            "Found %s stale failed tasks. Resetting them...", len(failed_tasks)
        )
        for task in failed_tasks:
            logger.debug("Resetting task #%s to PENDING.", task["id"])
            self.db.reset_task_status(task["id"])
            logger.info("Task #%s reset to PENDING.", task["id"])

    def _scan_issues(self):
        """Scan for open issues assigned to the bot."""
        self._scan_items(is_pr=False)

    def _scan_prs(self):
        """Scan for open Pull Requests assigned to the bot."""
        self._scan_items(is_pr=True)

    def _scan_items(self, is_pr: bool):
        """Generic scanner for issues and PRs."""
        config_data = self._get_scan_config(is_pr)

        logger.debug("Scanning for %s in organization: %s...", config_data["label"], config.git.org_name)
        items, err = get_assigned_items(
            org_name=config.git.org_name,
            bot_username=config.git.bot_username,
            is_pr=is_pr
        )

        if err:
            logger.debug("%s search failed. Error: %s", config_data["error_label"], err)
            return
        if not items:
            logger.debug("No %s found.", config_data["empty_label"])
            return

        logger.debug(
            "Found %s potential issue/PR items from GitHub search.", len(items)
        )

        for item in items:
            if item.get("isPullRequest", False) != is_pr:
                continue

            author_login = item.get("author", {}).get("login")
            if author_login not in config.git.authorized_users:
                logger.warning("Skipping unauthorized task from user: %s", author_login)
                continue

            self._process_scan_item(item, config_data, is_pr)

    def _get_scan_config(self, is_pr: bool) -> Dict[str, str]:
        """Returns configuration metadata for the scan type."""
        if is_pr:
            return {
                "label": "PRs",
                "error_label": "PR",
                "empty_label": "PRs",
                "task_label": "PR",
                "db_type": "PR"
            }
        return {
            "label": "issues",
            "error_label": "Issue",
            "empty_label": "issues",
            "task_label": "issue",
            "db_type": "ISSUE"
        }

    def _process_scan_item(self, item: Dict[str, Any], config_data: Dict[str, str], is_pr: bool):
        """Processes a single item found during scanning."""
        num = item["number"]
        repo_full_name = item["repository"]["nameWithOwner"]
        branch = self._resolve_branch_name(num, repo_full_name, is_pr)

        if not branch:
            return

        logger.debug(
            "Adding task for %s #%s: %s (branch: %s)",
            config_data["task_label"], num, repo_full_name, branch
        )
        self.db.add_task(
            config_data["db_type"],
            repo_full_name,
            f"https://github.com/{repo_full_name}",
            num,
            branch
        )

    def _resolve_branch_name(self, num: int, repo_full_name: str, is_pr: bool) -> Optional[str]:
        """Resolves the appropriate branch name for an issue or PR."""
        if is_pr:
            logger.debug("Fetching details for PR #%s to get head branch...", num)
            item_data = get_github_item(num, repo_full_name, item_type="pr", fields=["headRefName"])
            if not item_data:
                logger.debug("Could not fetch details for PR #%s. Skipping.", num)
                return None

            branch = item_data.get("headRefName")
            if not branch:
                logger.warning("Could not find headRefName for PR #%s.", num)
                return None
            return branch
        else:
            return f"issue-{num}"
