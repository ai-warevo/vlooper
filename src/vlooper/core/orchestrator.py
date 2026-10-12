"""The main orchestrator process for vLooper."""

import contextlib
import fcntl
import signal
import sys
import time
import json
from typing import Any, Dict

from vlooper.config import config
from vlooper.core.event_handlers.fixing_code_handler import FixingCodeHandler
from vlooper.core.event_handlers.git_isolated_handler import GitIsolatedHandler
from vlooper.core.event_handlers.github_notification_handler import (
    GitHubNotificationHandler,
)
from vlooper.core.event_handlers.github_pickup_handler import GitHubPickupHandler
from vlooper.core.event_handlers.pr_created_handler import PrCreatedHandler
from vlooper.core.event_handlers.task_status_handler import TaskStatusHandler
from vlooper.core.event_handlers.test_passed_handler import TestPassedHandler

# Framework imports
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.event_bus import EventBus
from vlooper.core.framework.events import EventName
from vlooper.core.framework.role_registry import registry
from vlooper.core.framework.synthesizer import Synthesizer
from vlooper.core.middleware.middleware_error_handler import (
    GlobalExceptionHandlerMiddleware,
)
from vlooper.core.middleware.middleware_github_auth import GitHubAuthCheckMiddleware
from vlooper.core.middleware.middleware_retry_limit import RetryLimitMiddleware
from vlooper.core.scanner import Scanner
from vlooper.infra.logger import get_logger
from vlooper.persistence.database import Database
from vlooper.services.scheduler_service import SchedulerService

# Import specialized agents
from vlooper.agents import (
    git_isolator_agent,
    issue_fetcher_agent,
    test_runner_agent,
    ai_fixer_agent,
    linter_bot_executor,
    coverage_booster_executor,
    test_healer_executor,
    review_fixer_executor,
    pr_reviewer_executor,
    github_pr_creator_executor,
)


logger = get_logger(__name__)


class VLooperOrchestrator:
    """
    The main orchestrator process for vLooper, responsible for polling for atomic steps
    and executing them using specialized roles.
    """

    def __init__(self) -> None:
        """Initializes the orchestrator internal state and bootstraps the registry."""
        # Infrastructure layers
        self.db = Database()
        self.event_bus = EventBus()
        self.scanner = Scanner(self.db, self.event_bus)
        self.synthesizer = Synthesizer()
        self.scheduler = SchedulerService(self.db)
        self.running = True
        self.lock_file = "/tmp/vlooper.lock"

        # Register post-step task handlers via EventBus (maintaining compatibility)
        status_handler = TaskStatusHandler(self.db)
        github_handler = GitHubNotificationHandler()
        github_pickup_handler = GitHubPickupHandler()
        git_isolated_handler = GitIsolatedHandler()
        test_passed_handler = TestPassedHandler()
        fixing_code_handler = FixingCodeHandler()
        pr_created_handler = PrCreatedHandler()

        self.event_bus.subscribe(EventName.TASK_FINISHED, status_handler.handle)
        self.event_bus.subscribe(EventName.TASK_FINISHED, github_handler.handle)
        self.event_bus.subscribe(EventName.TASK_PICKED_UP, github_pickup_handler.handle)
        self.event_bus.subscribe(EventName.GIT_ISOLATED, git_isolated_handler.handle)
        self.event_bus.subscribe(EventName.HARNESS_TEST_PASSED, test_passed_handler.handle)
        self.event_bus.subscribe(EventName.HARNESS_FIXING_CODE, fixing_code_handler.handle)
        self.event_bus.subscribe(EventName.GITHUB_PR_CREATED, pr_created_handler.handle)

        # Handle newly discovered tasks
        def handle_task_discovered(data: dict[str, Any]) -> None:
            self.scheduler.plan_initial_steps(data["task_id"], data["issue_data"])

        self.event_bus.subscribe(EventName.TASK_DISCOVERED, handle_task_discovered)

        # Bootstrap Role Registry
        self._bootstrap_roles()

        # Handle termination signals
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _bootstrap_roles(self) -> None:
        """Registers the agents in the registry."""
        logger.info("Bootstrapping role registry...")

        registry.register("git_isolator", git_isolator_agent)
        registry.register("issue_fetcher", issue_fetcher_agent)
        registry.register("test_runner", test_runner_agent)
        registry.register("ai_fixer", ai_fixer_agent)
        registry.register("pr_creator", github_pr_creator_executor) # Using the new agent for pr_creator

        # New specialized agents (returning direct dicts)
        registry.register("linter_bot", linter_bot_executor)
        registry.register("coverage_booster", coverage_booster_executor)
        registry.register("test_healer", test_healer_executor)
        registry.register("review_fixer", review_fixer_executor)
        registry.register("pr_reviewer", pr_reviewer_executor)
        registry.register("github_pr_creator", github_pr_creator_executor)

    def _handle_exit(self, _signum: int, _frame: Any) -> None:
        """Handles graceful shutdown on signals."""
        logger.info("\nStopping orchestrator...")
        self.running = False

    def _map_task_to_context(self, task: dict[str, Any]) -> TaskContext:
        """Maps a raw database task record into an isolated TaskContext instance."""
        return TaskContext(
            task_id=str(task["id"]),
            issue_number=(
                int(task["issue_number"]) if task["issue_number"] is not None else 0
            ),
            repo_url=str(task["repo_url"]),
            workspace_path=str(task.get("workspace_path", ".")),
            repo_full_name=task.get("repo_full_name"),
            branch_name=task.get("branch_name"),
            metadata={
                "event_bus": self.event_bus,  # Required for steps to emit events
                "original_task": task,  # Preserve original record if needed
            },
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
                logger.error("Another instance of vLooper is already running. Exiting.")
                sys.exit(1)

    def _process_step(self, step: dict[str, Any]) -> None:
        """Handles the execution of a single atomic step."""
        task = self.db.get_task_by_id(int(step["task_id"]))
        if not task:
            logger.error("Step #%s refers to non-existent task #%s", step["id"], step["task_id"])
            self.db.fail_step(int(step["id"]), "Task not found")
            return

        ctx = self._map_task_to_context(task)
        # Inject current step info into context metadata for visibility
        ctx.metadata["current_step"] = step

        role_name = step["role"]
        executor = registry.get_executor(role_name)
        if not executor:
            logger.error("No executor registered for role '%s'", role_name)
            self.db.fail_step(int(step["id"]), f"No executor for role {role_name}")
            return

        # Parse input data
        try:
            input_data = json.loads(step["input_data"]) if step["input_data"] else {}
        except json.JSONDecodeError as e:
            logger.error("Failed to parse step input_data: %s", e)
            self.db.fail_step(int(step["id"]), "Invalid input JSON")
            return

        # Prepare Mission Brief via Synthesizer with History
        history = self.db.get_completed_steps_for_task(int(step["task_id"]))
        brief = self.synthesizer.prepare_mission_brief(ctx, role_name, input_data, history=history)

        try:
            logger.info("[STEP] Executing role '%s' for task #%s (Step ID: %s)", 
                        role_name, ctx.task_id, step["id"])
            
            # Execute the specialized role function
            result = executor(ctx, brief)

            # Mark step as completed and save output
            self.db.complete_step(int(step["id"]), output_data=result)
            logger.info("[STEP] Role '%s' completed successfully.", role_name)

            # Reactive Re-planning Trigger for successful executions that contain failure metadata
            if isinstance(result, dict) and result.get("status") in ["failed", "error"]:
                self.scheduler.react_to_step_outcome(
                    int(step["id"]), 
                    int(step["task_id"]), 
                    role_name, 
                    step["order_index"], 
                    result
                )

            # Data Flow: Inject result into next step for this task, if it exists
            next_step = self.db.get_next_step_for_task(int(step["task_id"]), step["order_index"])
            if next_step:
                logger.debug("[FLOW] Injecting output of step #%s into next step #%s", 
                             step["id"], next_step["id"])
                self.db.update_step_input_data(int(next_step["id"]), result)
            else:
                # Check if task is finished (no more PENDING/RUNNING steps)
                # For simplicity in this phase, we check by seeing if there were any 
                # non-completed steps remaining.
                logger.info("[TASK] All steps for Task #%s appear to be finished.", ctx.task_id)

        except Exception as e:
            logger.exception("Error during execution of role '%s'", role_name)
            self.db.fail_step(int(step["id"]), str(e))
            # Reactive Re-planning Trigger for actual exceptions
            self.scheduler.react_to_step_outcome(
                int(step["id"]), 
                int(step["task_id"]), 
                role_name, 
                step["order_index"], 
                {"status": "error", "error_message": str(e)}
            )

    def _execute_loop(self, retry_failed: bool) -> None:
        """The main operational loop of the orchestrator."""
        while self.running:
            try:
                # Periodically scan for new tasks
                logger.debug("Performing periodic scan for new tasks...")
                self.scanner.scan(retry_failed=retry_failed)

                # Try to get next step (pending or failed)
                if retry_failed:
                    step = self.db.get_next_failed_step()
                else:
                    step = self.db.get_next_pending_step()

                if not step:
                    # No work found, sleep and try again
                    time.sleep(config.timeouts.loop_sleep_seconds)
                    continue

                self._process_step(step)

                # Small delay between steps to prevent database thrashing
                time.sleep(0.5)

            except Exception:
                logger.exception("Unexpected error in orchestrator loop")
                time.sleep(config.timeouts.error_wait_seconds)

    def run(self, retry_failed: bool = False) -> None:
        """Main execution loop."""
        try:
            with self._lock_context():
                mode = "RETRY" if retry_failed else "NORMAL"
                logger.info("vLooper Orchestrator started in %s mode.", mode)
                self._execute_loop(retry_failed)
                logger.info("Orchestrator shut down.")

        except Exception:
            logger.exception("Fatal error in orchestrator")


def main(retry_failed: bool = False) -> None:
    """Entry point for the orchestrator."""
    orchestrator = VLooperOrchestrator()
    orchestrator.run(retry_failed=retry_failed)


if __name__ == "__main__":
    main()
