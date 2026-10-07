"""Implementation of the agent-driven loop mechanism."""

import shlex

from vlooper.config import config
from vlooper.core.models import AttemptInfo, LoopState
from vlooper.processing import error_handler
from vlooper.utils import run_command


class AILoop:
    """Manages the iterative process of running an agent, testing results, and fixed errors."""

    def __init__(self, db, post_comment_callback):
        self.db = db
        self._post_github_comment = post_comment_callback

    def run_opencode_loop(self, task, task_id, ctx, repo_dir):
        """Run the agent-driven loop: Write -> Test -> Fix."""
        max_attempts = config.max_retries + 1
        error_summaries = []
        state = LoopState(ctx=ctx)

        for attempt in range(1, max_attempts + 1):
            pre_attempt_status, _ = run_command(
                ["git", "status", "--porcelain"], cwd=repo_dir
            )

            if attempt > 1:
                self._notify_retry_attempt(task, attempt, max_attempts)

            # 1. Run Opencode (Agent execution)
            err = self._execute_opencode_agent(state.ctx, repo_dir)

            if err:
                print(f"⚠️ Opencode error on attempt {attempt}: {err}")
                attempt_info = AttemptInfo(
                    task_id=task_id,
                    attempt=attempt,
                    pre_attempt_status=pre_attempt_status,
                    repo_dir=repo_dir,
                )
                is_stuck = self._handle_attempt_failure(
                    err=err,
                    info=attempt_info,
                    error_summaries=error_summaries,
                    state=state,
                )
                if is_stuck:
                    break
                continue

            # 2. Run Tests
            test_err = self._execute_tests(repo_dir)

            if test_err is None:
                print(f"🎉 Tests passed on attempt {attempt}!")
                return True

            # Step C (Evaluate/Feedback) - Failure logic
            print(f"❌ Tests failed on attempt {attempt}.")
            attempt_info = AttemptInfo(
                task_id=task_id,
                attempt=attempt,
                pre_attempt_status=pre_attempt_status,
                repo_dir=repo_dir,
            )
            is_stuck = self._handle_attempt_failure(
                err=test_err,
                info=attempt_info,
                error_summaries=error_summaries,
                state=state,
            )
            if is_stuck:
                break

        return False

    def _notify_retry_attempt(self, task, attempt, max_attempts):
        """Print and post a comment about the retry status."""
        print(f"🔄 Attempt {attempt}/{max_attempts}...")
        self._post_github_comment(
            task, f"🛠️ Attempt {attempt}/{max_attempts} failed. Retrying..."
        )

    def _execute_opencode_agent(self, ctx, repo_dir):
        """Run the Opencode agent command and return any stderr/error content."""
        print("🤖 Running Opencode agent...")
        opencode_cmd = ["opencode", "run", "--model", config.model, ctx]
        _, err = run_command(
            opencode_cmd,
            cwd=repo_dir,
            timeout=config.opencode_run_timeout,
            truncate_lines=50,
        )
        return err

    def _execute_tests(self, repo_dir):
        """Run the configured test suite command and return any stderr/error content."""
        print(f"🧪 Running tests: {config.test_command}")
        _, test_err = run_command(
            shlex.split(config.test_command),
            cwd=repo_dir,
            timeout=config.test_run_timeout,
            truncate_lines=50,
        )
        return test_err

    def _handle_attempt_failure(
        self,
        err,
        info: AttemptInfo,
        error_summaries,
        state: LoopState,
    ):
        """Process an execution/test error, check if the agent is stuck, and update state."""
        snip = error_handler.truncate_output(err, lines=15)
        post_attempt_status, _ = run_command(
            ["git", "status", "--porcelain"], cwd=info.repo_dir
        )
        made_changes = post_attempt_status != info.pre_attempt_status

        summary = error_handler.get_error_summary(snip)
        cleaned_snip = error_handler.clean_snippet(snip)

        is_loop = error_handler.check_error_loop(summary, cleaned_snip, error_summaries)
        if not is_loop:
            error_summaries.append((summary, cleaned_snip))

        is_stuck = (
            is_loop
            or error_handler.is_stuck(snip, state.last_err_snip)
            or (info.attempt > 1 and not made_changes)
        )
        state.consecutive_errs = state.consecutive_errs + 1 if is_stuck else 1
        state.last_err_snip = snip

        if state.consecutive_errs >= 2:
            print("🚨 Agent stuck! Loop detected or same error twice. Breaking loop.")
            self.db.fail_task(info.task_id, err)
            return True

        state.ctx += "\nThe previous attempt failed with the following errors:"
        state.ctx += f"\n{err}\nPlease fix these issues and try again."
        self.db.fail_task(info.task_id, err)

        return False
