"""The main orchestrator process for vLooper."""

import contextlib
import fcntl
import signal
import sys
import time
import json
from typing import Any, Dict

from vlooper.config import config
from vlooper.agents.utility.task_completion_agent import TaskCompletionAgent
from vlooper.agents.utility.telemetry_agent import TelemetryAgent

# Framework imports
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.role_registry import registry, Agent
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
from vlooper.services.github_service import post_github_comment

from vlooper.agents import (
    git_isolator_agent,
    issue_fetcher_agent,
    test_runner_agent,
    ai_fixer_agent,
    linter_bot_agent,
    coverage_booster_agent,
    test_healer_agent,
    review_fixer_agent,
    pr_reviewer_agent,
    github_pr_creator_agent,
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
        self.scanner = Scanner(self.db)
        self.synthesizer = Synthesizer()
        self.scheduler = SchedulerService(self.db)
        self.running = True
        self.lock_file = "/tmp/vlooper.lock"

        # Specialized Agents for Orchestration
        self.task_completion_agent = TaskCompletionAgent()
        self.telemetry_agent = TelemetryAgent()

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
        registry.register("pr_creator", github_pr_creator_agent)

        # New specialized agents (returning direct dicts)
        registry.register("linter_bot", linter_bot_agent)
        registry.register("coverage_booster", coverage_booster_agent)
        registry.register("test_healer", test_healer_agent)
        registry.register("review_fixer", review_fixer_agent)
        registry.register("pr_reviewer", pr_reviewer_agent)
        registry.register("github_pr_creator", github_pr_creator_agent)

    def _handle_exit(self, _signum: int, _frame: Any) -> None:
        """Handles graceful shutdown on signals."""
        logger.info("\nStopping orchestrator...")
        self.running = False

    def _map_task_to_context(self, task: dict[str, Any], completed_steps: list[dict[str, Any]]) -> TaskContext:
        """Maps a raw database task record into an isolated TaskContext instance.
        Uses completed_steps to reconstruct the context state (workspace, branch, etc.).
        """
        # Parse meta if available
        meta = {}
        if task.get("meta"):
            try:
                meta = json.loads(task["meta"])
            except Exception:
                logger.warning("Failed to parse task meta for Task #%s", task["id"])

        ctx = TaskContext(
            task_id=str(task["id"]),
            task_type=task.get("task_type", "ISSUE"),
            issue_number=(
                int(task["issue_number"]) if task["issue_number"] is not None else 0
            ),
            repo_url=str(task["repo_url"]),
            workspace_path=str(task.get("workspace_path", ".")),
            repo_full_name=task.get("repo_full_name"),
            branch_name=task.get("branch_name"),
            status=task.get("status", "PENDING"),
            issue_title=meta.get("issue_title"),
            issue_body=meta.get("issue_body"),
            metadata={
                "original_task": task,
            },
        )

        # Reconstruct context from previous completed steps to support retries/resumes
        try:
            for step in completed_steps:
                raw_output = step.get("output_data")
                if not raw_output:
                    continue

                # Parse the JSON output from the database
                try:
                    output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
                except (json.JSONDecodeError, TypeError):
                    continue

                # Handle both direct dicts and "status/output" wrappers commonly used by agents
                data_to_apply = output.get("output") if isinstance(output, dict) and "output" in output else output

                if not isinstance(data_to_apply, dict):
                    continue

                # Apply updates to the context from step results
                if "workspace_path" in data_to_apply:
                    ctx.workspace_path = str(data_to_apply["workspace_path"])
                if "branch_name" in data_to_apply:
                    ctx.branch_name = str(data_to_apply["branch_name"])
                if "repo_full_name" in data_to_apply:
                    ctx.repo_full_name = str(data_to_apply["repo_full_name"])
                if "pr_details" in data_to_apply:
                    ctx.pr_details = data_to_apply["pr_details"]

        except Exception as e:
            logger.error("Failed to reconstruct context from completed steps: %s", e)

        return ctx

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

        history = self.db.get_completed_steps_for_task(int(step["task_id"]))
        ctx = self._map_task_to_context(task, history)

        if not history:
            try:
                task_data = {
                    "repo_full_name": ctx.repo_full_name,
                    "task_type": ctx.task_type,
                    "branch_name": ctx.branch_name,
                }
                post_github_comment(task_data, "🤖 vLooper has picked up this task.")
            except Exception as e:
                logger.error("Failed to post 'started' comment for Task #%s: %s", ctx.task_id, e)

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
        brief = self.synthesizer.prepare_mission_brief(ctx, role_name, input_data, history=history)
        # Inject brief into context metadata for Agent objects to use
        ctx.metadata["mission_brief"] = brief

        try:
            # Execute the specialized role (function or Agent object)
            if isinstance(executor, Agent):
                result = executor.execute(ctx)
            else:
                result = executor(ctx, brief)

            # Mark step as completed and save output
            self.db.complete_step(int(step["id"]), output_data=result)
            logger.info("[STEP] Role '%s' completed successfully.", role_name)

            # Reactive Re-planning Trigger for successful executions that contain failure metadata
            if isinstance(result, dict) and result.get("status") in ["failed", "error"]:
                recovered = self.scheduler.react_to_step_outcome(
                    int(step["id"]), 
                    int(step["task_id"]), 
                    role_name, 
                    step["order_index"], 
                    result
                )
                if not recovered:
                    logger.error("[STEP] Role '%s' failed and no recovery was possible.", role_name)
                    ctx.error = result.get("error") or result.get("message")
                    ctx.is_aborted = True
                    ctx.exit_code = 1

                    # Finalize Task
                    if ctx.is_aborted or (ctx.exit_code is not None and ctx.exit_code != 0):
                        error_msg = str(ctx.error) if ctx.error else f"Pipeline failed with exit code {ctx.exit_code}"
                        logger.info("Finalizing task #%s as FAILED: %s", ctx.task_id, error_msg)
                        self.db.fail_task(ctx.task_id, error_msg)
                    else:
                        logger.info("Finalizing task #%s as COMPLETED.", ctx.task_id)
                        self.db.complete_task(ctx.task_id)

                    # Notify via Agents
                    self.task_completion_agent.execute(ctx)
                    if ctx.pr_details:
                        self.telemetry_agent.execute(ctx)
                    return

            # Data Flow: Inject result into next step for this task, if it exists
            next_step = self.db.get_next_step_for_task(int(step["task_id"]), step["order_index"])
            if next_step:
                logger.debug("[FLOW] Injecting output of step #%s into next step #%s", 
                             step["id"], next_step["id"])
                self.db.update_step_input_data(int(next_step["id"]), result)
            else:
                # Check if task is finished (no more PENDING/RUNNING steps)
                logger.info("[TASK] All steps for Task #%s appear to be finished.", ctx.task_id)

                if isinstance(result, dict) and result.get("status") in ["failed", "error"]:
                    ctx.error = result.get("error") or result.get("message")
                    ctx.is_aborted = True
                    ctx.exit_code = 1
                else:
                    ctx.exit_code = 0

                # Finalize Task
                if ctx.is_aborted or (ctx.exit_code is not None and ctx.exit_code != 0):
                    error_msg = str(ctx.error) if ctx.error else f"Pipeline failed with exit code {ctx.exit_code}"
                    logger.info("Finalizing task #%s as FAILED: %s", ctx.task_id, error_msg)
                    self.db.fail_task(ctx.task_id, error_msg)
                else:
                    logger.info("Finalizing task #%s as COMPLETED.", ctx.task_id)
                    self.db.complete_task(ctx.task_id)

                # Notify via Agents
                self.task_completion_agent.execute(ctx)
                if ctx.pr_details:
                    self.telemetry_agent.execute(ctx)

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
                newly_discovered = self.scanner.scan(retry_failed=retry_failed)
                for task_info in newly_discovered:
                    task_id = task_info["task_id"]
                    if self.db.claim_task(task_id):
                        self.scheduler.plan_initial_steps(task_id, task_info["issue_data"])

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
