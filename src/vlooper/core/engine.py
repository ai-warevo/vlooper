"""TaskEngine module to orchestrate task execution."""

import logging

from vlooper.config import config
from vlooper.core import error_handler
from vlooper.core.exceptions import VLooperError
from vlooper.core.loop import AILoop
from vlooper.database import Database
from vlooper.integrations import git_manager
from vlooper.integrations import github_interaction as interaction
from vlooper.logger import get_logger

logger = get_logger(__name__)


class TaskEngine:  # pylint: disable=too-few-public-methods
    """TaskEngine to handle task execution and GitHub interactions."""

    def __init__(self, db: Database):
        """Initialize the engine with a database instance."""
        self.db = db
        self.ai_loop = AILoop(db, self._post_github_comment)

    def _post_github_comment(self, task, message):
        """Helper to post a comment to the respective GitHub issue or PR."""
        interaction.post_github_comment(task, message)

    def _get_github_author(self, task):
        """Fetch the author of the issue/PR to mention them."""
        return interaction.get_github_author(task)

    def process_next_task(self) -> bool:
        """Process the next pending task from the database."""
        tasks = self.db.get_pending_tasks()
        if not tasks:
            logger.debug("No pending tasks found in database.")
            return False

        # Pick the first pending task
        task = tasks[0]
        task_id = task["id"]

        logger.info(
            f"🛠 Picking up task #{task_id}: {task['task_type']} in "
            f"{task['repo_full_name']} (branch: {task['branch_name']})"
        )
        logger.debug(f"Task payload for #{task_id}: {task}")

        if not self.db.claim_task(task_id):
            logger.warning(f"Failed to claim task #{task_id}. It might have been picked up by another instance.")
            return False  # Someone else claimed it

        logger.debug(f"Successfully claimed task #{task_id}.")

        # Post 'Started' comment
        self._post_github_comment(task, "🤖 vLooper has picked up this task.")

        try:
            logger.debug(f"Executing task #{task_id}...")
            success, pr_number = self._execute_task(task, task_id)
            if success:
                self.db.complete_task(task_id)
                # Post finishing comment (for issues or PRs)
                mention = self._get_github_author(task)
                pr_suffix = f" #{pr_number}" if pr_number else ""
                self._post_github_comment(
                    task,
                    f"✅ Task completed successfully!\n@{mention} check this out:{pr_suffix}",
                )
                logger.info(f"✅ Task #{task_id} completed successfully.")
            else:
                raise VLooperError("Task execution failed (see logs).")
        except Exception as e:  # noqa: W0718
            error_msg = str(e)
            logger.error(f"❌ Task #{task_id} failed: {error_msg}")
            self.db.fail_task(task_id, error_msg)

            if self._is_terminal_failure(task_id):
                logger.warning(
                    f"📢 Task #{task_id} reached terminal failure. Escalating..."
                )
                self._post_escalation_comment(task, error_msg)

            return False

        return True

    def _is_terminal_failure(self, task_id) -> bool:
        """Check if the task has exhausted all retries."""
        return self.db.is_task_at_max_retries(task_id)

    def _post_escalation_comment(self, task, last_error):
        """Post a final failure comment tagging the user."""
        mention = self._get_github_author(task)

        msg = (
            f"🚨 **vLooper Escalation** 🚨\n\n"
            f"I have attempted to solve this task {config.max_retries + 1} times but failed.\n"
            f"**Last Error:** `{last_error}`\n\n"
            f"Please take manual action. @{mention}"
        )

        self._post_github_comment(task, msg)

    def _execute_task(self, task, task_id):
        """Execute the task details."""
        repo_full_name = task["repo_full_name"]
        branch_name = task["branch_name"]
        task_type = task["task_type"]
        repo_short_name = repo_full_name.split("/")[-1]

        context = self._get_context(task, repo_full_name)
        if not context:
            return False, None

        commit_msg = self._generate_commit_message(task, branch_name)

        # 1 & 2 & 3. Setup workspace and branch
        repo_dir = self._prepare_repo_dir(repo_full_name, repo_short_name)
        if not repo_dir:
            return False, None

        try:
            if not self._setup_branch(repo_dir, branch_name, task_type):
                return False, None

            # 4. Run Opencode Loop
            success = self.ai_loop.run_opencode_loop(task, task_id, context, repo_dir)
            if not success:
                raise VLooperError(
                    "Task failed after reaching maximum attempts or getting stuck."
                )

            # 5 & 6. Commit, Push and Create PR (Delivery)
            pr_number = None
            try:
                if not self._commit_and_push(repo_dir, branch_name, commit_msg):
                    return False, None

                # 6. Create PR if it was an issue
                if task_type == "ISSUE":
                    pr_number = self._create_pr(repo_full_name, repo_dir, branch_name)
                elif task_type == "PR":
                    # Try to find existing PR number for a refinement task
                    try:
                        details = interaction.get_pr_details(
                            repo_full_name, branch_name
                        )
                        if details:
                            pr_number = details[0]
                    except Exception as e:
                        logger.warning(f"⚠️ Could not retrieve PR details: {e}")
            except VLooperError:
                self._stash_and_checkout_main(repo_dir)
                raise

            return True, pr_number
        finally:
            self._delete_local_branch(repo_dir, branch_name)
            self._delete_remote_branch(repo_dir, branch_name)

    def _generate_commit_message(self, task, branch_name):
        task_type = task["task_type"]
        if task_type == "ISSUE":
            try:
                num = branch_name.split("-")[-1]
                return f"fix #{num}"
            except Exception:  # noqa: W0718
                return "fix issue"
        return f"refactor PR on {branch_name}"

    def _prepare_repo_dir(self, repo_full_name, repo_short_name):
        return git_manager.prepare_repo_dir(repo_full_name, repo_short_name)

    def _setup_branch(self, repo_dir, branch_name, task_type):
        return git_manager.setup_branch(repo_dir, branch_name, task_type)

    def _is_stuck(self, new_snip: str, last_err_snip: str | None) -> bool:
        """Check if the agent is stuck."""
        return error_handler.is_stuck(new_snip, last_err_snip)

    def _commit_and_push(self, repo_dir, branch_name, commit_msg):
        return git_manager.commit_and_push(repo_dir, branch_name, commit_msg)

    def _create_pr(self, repo_full_name, repo_dir, branch_name):
        return interaction.create_pr(repo_full_name, repo_dir, branch_name)

    def _stash_and_checkout_main(self, repo_dir):
        git_manager.stash_and_checkout_main(repo_dir)

    def _delete_local_branch(self, repo_dir, branch_name):
        git_manager.delete_local_branch(repo_dir, branch_name)

    def _delete_remote_branch(self, repo_dir, branch_name):
        git_manager.delete_remote_branch(repo_dir, branch_name)

    def _get_context(self, task, repo_full_name):
        """Fetch context for the task from GitHub."""
        if task["task_type"] == "ISSUE":
            return self._get_issue_context(task, repo_full_name)
        return self._get_pr_context(task, repo_full_name)

    def _get_issue_context(self, task, repo_full_name):
        return interaction.get_issue_context(task, repo_full_name)

    def _get_pr_context(self, task, repo_full_name):
        return interaction.get_pr_context(task, repo_full_name)
