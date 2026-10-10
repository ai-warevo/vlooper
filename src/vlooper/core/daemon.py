"""The main daemon process for vLooper."""

import fcntl
import signal
import sys
import time
from typing import Any, Dict, Optional

from vlooper.config import config
from vlooper.database import Database
from vlooper.logger import get_logger
from vlooper.core.scanner import Scanner

# Framework imports
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.event_bus import EventBus
from vlooper.core.framework.pipeline import TaskPipeline

# Step and Middleware imports
from vlooper.core.middleware.middleware_error_handler import GlobalExceptionHandlerMiddleware
from vlooper.core.middleware.middleware_github_auth import GitHubAuthCheckMiddleware
from vlooper.core.middleware.middleware_retry_limit import RetryLimitMiddleware
from vlooper.core.steps.step_git_isolate import git_isolate_repository
from vlooper.core.steps.step_run_tests import run_repository_tests
from vlooper.core.steps.step_apply_fix import apply_ai_fix
from vlooper.core.steps.step_github_pr import github_create_pull_request
from vlooper.services.github_service import post_github_comment

logger = get_logger(__name__)


class VLooperDaemon:
    """
    The main daemon process for vLooper, responsible for polling task targets 
    and bootstrapping the automated execution pipeline.
    
    This class follows a declarative architecture where it initializes the 
    TaskPipeline with a predefined stack of middlewares and automation steps. 
    It does not contain any business logic; instead, it acts as the orchestration 
    layer that bridges the database/scanning layer with the execution engine.
    """

    def __init__(self) -> None:
        """Initializes the daemon internal state and bootstraps the pipeline."""
        # Infrastructure layers
        self.db = Database()
        self.scanner = Scanner(self.db)
        self.event_bus = EventBus()
        self.running = True
        self.lock_file = "/tmp/vlooper.lock"

        # Core Pipeline Bootstrap
        self.pipeline = self._bootstrap_pipeline()

        # Handle termination signals
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _bootstrap_pipeline(self) -> TaskPipeline:
        """
        Declaratively configures the central task pipeline with its 
        middleware onion layers and sequential execution steps.
        """
        return (
            TaskPipeline(self.event_bus)
            # Middleware Layering (Outer to Inner)
            .use(GlobalExceptionHandlerMiddleware())  # Catches unforeseen bugs
            .use(GitHubAuthCheckMiddleware())         # Fails early if tokens missing
            .use(RetryLimitMiddleware(max_pipeline_attempts=config.max_pipeline_attempts)) # Controls test-fix retries

            # Execution Step Sequencing (Core Work)
            .add_step(git_isolate_repository)        # 1. Setup workspace/branch
            .add_step(run_repository_tests)          # 2. Run the harness
            .add_step(apply_ai_fix)                  # 3. Fix if tests failed
            .add_step(github_create_pull_request)    # 4. Push and PR
        )

    def _handle_exit(self, _signum: int, _frame: Any) -> None:
        """Handles graceful shutdown on signals."""
        logger.info("\n🛑 Stopping daemon...")
        self.running = False

    def _map_task_to_context(self, task: Dict[str, Any]) -> TaskContext:
        """Maps a raw database task record into an isolated TaskContext instance."""
        return TaskContext(
            task_id=str(task["id"]),
            issue_number=int(task["issue_number"]) if task["issue_number"] is not None else 0,
            repo_url=str(task["repo_url"]),
            metadata={
                "event_bus": self.event_bus,  # Required for steps to emit events
                "original_task": task         # Preserve original record if needed
            }
        )

    def _update_task_status(self, ctx: TaskContext) -> None:
        """
        Updates the database with final results from the pipeline execution.
        Determines status based on context flags and exit codes.
        """
        try:
            if ctx.is_aborted or (ctx.exit_code is not None and ctx.exit_code != 0):
                error_msg = str(ctx.error) if ctx.error else f"Pipeline failed with exit code {ctx.exit_code}"
                logger.info("📝 Finalizing task #%s as FAILED: %s", ctx.task_id, error_msg)
                self.db.fail_task(ctx.task_id, error_msg)
            else:
                logger.info("📝 Finalizing task #%s as COMPLETED.", ctx.task_id)
                self.db.complete_task(ctx.task_id)
        except Exception as e:
            logger.error("❌ Failed to update database for task #%s: %s", ctx.task_id, e)

    def _post_completion_comment(self, ctx: TaskContext) -> None:
        """Posts a summary comment to the GitHub issue/PR after pipeline completion."""
        # Construct task data for the legacy helper function
        task_data = {
            "repo_full_name": ctx.metadata.get("repo_full_name"),
            "task_type": ctx.metadata["original_task"]["task_type"],
            "branch_name": ctx.branch_name,
        }

        # Ensure we have the necessary info to identify the issue/PR
        if not task_data["repo_full_name"] or not task_data["branch_name"]:
            logger.warning("⚠️ Cannot post GitHub comment: missing repo_full_name or branch_name in context.")
            return

        try:
            if ctx.exit_code == 0:
                # Successful completion
                message = "✅ **vLooper Automation Complete!**\n\nThe automated fix has been applied and a Pull Request has been created."
                if hasattr(ctx, 'pr_details') and ctx.pr_details:
                     url = ctx.pr_details.get('html_url', '')
                     if url:
                         message += f"\n\n🔗 **Pull Request:** {url}"
                
                logger.info("💬 Posting success comment to GitHub...")
                post_github_comment(task_data, message)
            else:
                # Failure (either aborted or exit code != 0)
                error_msg = str(ctx.error) if ctx.error else f"Pipeline failed with exit code {ctx.exit_code}"
                message = f"❌ **vLooper Automation Failed**\n\nAn error occurred during the automated cycle:\n`{error_msg}`"
                
                logger.info("💬 Posting failure comment to GitHub...")
                post_github_comment(task_data, message)

        except Exception as e:
            logger.error("❌ Failed to post completion comment to GitHub: %s", e)

    def run(self, retry_failed: bool = False) -> None:
        """
        Main execution loop that polls for tasks and runs the pipeline.

        Args:
            retry_failed: If True, only poll for tasks marked as FAILED in the DB.
        """
        logger.debug("Using lock file: %s", self.lock_file)

        # Attempt to acquire an exclusive lock on the lock file
        with open(self.lock_file, "w", encoding="utf-8") as lock_fd:
            try:
                logger.debug("Attempting to acquire file lock...")
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("Lock acquired successfully.")
            except OSError:
                logger.error("❌ Another instance of vLooper is already running. Exiting.")
                sys.exit(1)

            logger.info(
                "🚀 vLooper Daemon started with lock acquired. (Retry mode: %s)",
                retry_failed,
            )

            while self.running:
                try:
                    # 1. Scan for new tasks (updates internal DB state/flags)
                    logger.debug("--- Starting iteration (scanning for tasks) ---")
                    self.scanner.scan(retry_failed=retry_failed)

                    # 2. Retrieve the next available task to process
                    if retry_failed:
                        logger.debug("Mode [Retry]: Querying failed tasks...")
                        tasks = self.db.get_failed_tasks()
                    else:
                        logger.debug("Mode [Normal]: Querying pending tasks...")
                        tasks = self.db.get_pending_tasks()

                    task = None
                    if tasks:
                        task = tasks[0]
                    
                    if not task:
                        logger.debug("No active tasks found in this scan. Sleeping for %ss...", config.loop_sleep_seconds)
                        time.sleep(config.loop_sleep_seconds)
                        continue

                    # 3. Execute the Pipeline for the task
                    logger.info("🎯 Target identified: Task #%s (Type: %s, Repo: %s)", task["id"], task["task_type"], task["repo_full_name"])
                    
                    # Mark as being processed in DB before running to prevent double-claiming
                    logger.debug("Attempting to claim task #%s...", task["id"])
                    if not self.db.claim_task(task["id"]):
                        logger.debug("Task #%s already claimed or ineligible (max retries reached). Skipping.", task["id"])
                        continue

                    logger.info("⚙️ Task #%s claimed successfully. Initializing pipeline context...", task["id"])
                    ctx = self._map_task_to_context(task)
                    
                    logger.info("🔥 Executing pipeline for Task #%s (Issue #%s)...", ctx.task_id, ctx.issue_number)
                    self.pipeline.run(ctx)

                    # 4. Sync final results back to Database
                    logger.info("🔄 Pipeline finished for task #%s. Synchronizing results with DB...", ctx.task_id)
                    self._update_task_status(ctx)

                    # Post completion comment to GitHub
                    self._post_completion_comment(ctx)

                    # Sleep between iterations
                    logger.debug("Iteration complete. Sleeping...")
                    time.sleep(config.loop_sleep_seconds)

                except Exception as e:
                    logger.error("⚠️ Unexpected error in daemon loop: %s", e, exc_info=True)
                    logger.debug("Sleeping for error recovery period (%ss)...", config.error_wait_seconds)
                    time.sleep(config.error_wait_seconds)

        logger.info("👋 Daemon shut down.")


def main(retry_failed: bool = False) -> None:
    """Entry point for the daemon."""
    daemon = VLooperDaemon()
    daemon.run(retry_failed=retry_failed)


if __name__ == "__main__":
    # In a real production environment, arguments would be parsed from sys.argv
    main()
