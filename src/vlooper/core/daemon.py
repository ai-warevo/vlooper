"""The main daemon process for vLooper."""

import contextlib
import fcntl
import signal
import sys
import time
from typing import Any, Dict, Optional

from vlooper.config import config
from vlooper.persistence.database import Database
from vlooper.infra.logger import get_logger
from vlooper.core.scanner import Scanner
from vlooper.core.event_handlers.task_status_handler import TaskStatusHandler
from vlooper.core.event_handlers.github_notification_handler import GitHubNotificationHandler
from vlooper.core.event_handlers.git_isolated_handler import GitIsolatedHandler
from vlooper.core.event_handlers.test_passed_handler import TestPassedHandler
from vlooper.core.event_handlers.fixing_code_handler import FixingCodeHandler
from vlooper.core.event_handlers.pr_created_handler import PrCreatedHandler
from vlooper.core.framework.events import EventName

# Framework imports
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.event_bus import EventBus
from vlooper.core.framework.pipeline import TaskPipeline
from vlooper.core.middleware.middleware_error_handler import GlobalExceptionHandlerMiddleware
from vlooper.core.middleware.middleware_github_auth import GitHubAuthCheckMiddleware
from vlooper.core.middleware.middleware_retry_limit import RetryLimitMiddleware
from vlooper.core.steps.step_git_isolate import git_isolate_repository
from vlooper.core.steps.step_run_tests import run_repository_tests
from vlooper.core.steps.step_apply_fix import apply_ai_fix
from vlooper.core.steps.step_github_pr import github_create_pull_request

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

        # Register post-pipeline task handlers via EventBus
        status_handler = TaskStatusHandler(self.db)
        github_handler = GitHubNotificationHandler()
        git_isolated_handler = GitIsolatedHandler()
        test_passed_handler = TestPassedHandler()
        fixing_code_handler = FixingCodeHandler()
        pr_created_handler = PrCreatedHandler()

        self.event_bus.subscribe(EventName.TASK_FINISHED, status_handler.handle)
        self.event_bus.subscribe(EventName.TASK_FINISHED, github_handler.handle)
        self.event_bus.subscribe(EventName.GIT_ISOLATED, git_isolated_handler.handle)
        self.event_bus.subscribe(EventName.HARNESS_TEST_PASSED, test_passed_handler.handle)
        self.event_bus.subscribe(EventName.HARNESS_FIXING_CODE, fixing_code_handler.handle)
        self.event_bus.subscribe(EventName.GITHUB_PR_CREATED, pr_created_handler.handle)

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
            .use(RetryLimitMiddleware(max_pipeline_attempts=config.timeouts.max_pipeline_attempts)) # Controls test-fix retries

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

    @contextlib.contextmanager
    def _lock_context(self):
        """Context manager to handle exclusive file locking."""
        logger.debug("Using lock file: %s", self.lock_file)
        with open(self.lock_file, "w", encoding="utf-8") as lock_fd:
            try:
                logger.debug("Attempting to acquire file lock...")
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("Lock acquired successfully.")
                yield lock_fd
            except OSError:
                logger.error("❌ Another instance of vLooper is already running. Exiting.")
                sys.exit(1)

    def _get_next_task(self, retry_failed: bool) -> Optional[Dict[str, Any]]:
        """Scans and retrieves the next available task."""
        logger.debug("--- Starting iteration (scanning for tasks) ---")
        self.scanner.scan(retry_failed=retry_failed)

        if retry_failed:
            logger.debug("Mode [Retry]: Querying failed tasks...")
            tasks = self.db.get_failed_tasks()
        else:
            logger.debug("Mode [Normal]: Querying pending tasks...")
            tasks = self.db.get_pending_tasks()

        return tasks[0] if tasks else None

    def _process_task(self, task: Dict[str, Any]) -> None:
        """Handles the end-to-end lifecycle of a single task."""
        logger.info("🎯 Target identified: Task #%s (Type: %s, Repo: %s)", 
                    task["id"], task["task_type"], task["repo_full_name"])

        # Mark as being processed in DB before running to prevent double-claiming
        logger.debug("Attempting to claim task #%s...", task["id"])
        if not self.db.claim_task(task["id"]):
            logger.debug("Task #%s already claimed or ineligible (max retries reached). Skipping.", task["id"])
            return

        logger.info("⚙️ Task #%s claimed successfully. Initializing pipeline context...", task["id"])
        ctx = self._map_task_to_context(task)

        logger.info("🔥 Executing pipeline for Task #%s (Issue #%s)...", ctx.task_id, ctx.issue_number)
        self.pipeline.run(ctx)

        # Emit task completion event to trigger post-processing (DB sync, notifications, etc.)
        self.event_bus.emit(EventName.TASK_FINISHED, ctx)

    def _execute_loop(self, retry_failed: bool) -> None:
        """The main operational loop of the daemon."""
        while self.running:
            try:
                task = self._get_next_task(retry_failed)

                if not task:
                    logger.debug("No active tasks found in this scan. Sleeping for %ss...", config.timeouts.loop_sleep_seconds)
                    time.sleep(config.timeouts.loop_sleep_seconds)
                    continue

                self._process_task(task)

                # Sleep between iterations
                logger.debug("Iteration complete. Sleeping...")
                time.sleep(config.timeouts.loop_sleep_seconds)

            except Exception as e:
                logger.error("⚠️ Unexpected error in daemon loop: %s", e, exc_info=True)
                logger.debug("Sleeping for error recovery period (%ss)...", config.timeouts.error_wait_seconds)
                time.sleep(config.timeouts.error_wait_seconds)

    def run(self, retry_failed: bool = False) -> None:
        """
        Main execution loop that orchestrates task scanning and processing.

        Args:
            retry_failed: If True, only poll for tasks marked as FAILED in the DB.
        """
        try:
            with self._lock_context():
                logger.info(
                    "🚀 vLooper Daemon started with lock acquired. (Retry mode: %s)",
                    retry_failed,
                )

                self._execute_loop(retry_failed)
                logger.info("👋 Daemon shut down.")

        except SystemExit:
            raise
        except Exception as e:
            logger.error("❌ Fatal error in daemon: %s", e, exc_info=True)


def main(retry_failed: bool = False) -> None:
    """Entry point for the daemon."""
    daemon = VLooperDaemon()
    daemon.run(retry_failed=retry_failed)


if __name__ == "__main__":
    # In a real production environment, arguments would be parsed from sys.argv
    main()
