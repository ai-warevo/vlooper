\"\"\"Implementation of the agent-driven loop mechanism.\"\"\"

import shlex
import logging

from vlooper.config import config
from vlooper.core import error_handler
from vlooper.core.models import AttemptInfo, LoopState
from vlooper.utils import run_command
from vlooper.logger import get_logger


logger = get_logger(__name__)


class AILoop:
    \"\"\"Manages the iterative process of running an agent, testing results, and fixed errors.\"\"\"

    def __init__(self, db, post_comment_callback):
        self.db = db
        self._post_github_comment = post_comment_callback

    def run_opencode_loop(self, task, task_id, ctx, repo_dir):
        \"\"\"Run the agent-driven loop: Write -> Test -> Fix.\"\"\"
        max_attempts = config.max_retries + 1
        error_summaries = []
        state = LoopState(ctx=ctx)

        logger.debug(f\"Starting Opencode loop for task #{task_id}. Max attempts: {max_attempts}\")

        for attempt in range(1, max_attempts + 1):
            logger.debug(f\"Starting attempt {attempt}/{max_attempts} for task #{task_id}.\")
            pre_attempt_status, _ = run_command(
                [\"git\", \"status\", \"--porcelain\"], cwd=repo_dir
            )
            logger.debug(f\"Pre-attempt git status: {pre_attempt_status if pre_attempt_status else 'Clean'}\")

            if attempt > 1:
                self._notify_retry_attempt(task, attempt, max_attempts)

            # 1. Run Opencode (Agent execution)
            logger.debug(f\"[Attempt {attempt}] Running agent tool execution...\")
            err = self._execute_opencode_agent(state.ctx, repo_dir)

            if err:
                logger.warning(f\"⚠️ Opencode error on attempt {attempt}: {err}\")
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
                    logger.debug(\"Loop broken because agent was considered stuck.\")
                    break
                continue

            # 2. Run Tests
            logger.debug(f\"[Attempt {attempt}] Agent execution successful. Starting tests...\")
            test_err = self._execute_tests(repo_dir)

            if test_err is None:
                logger.info(f\"🎉 Tests passed on attempt {attempt}!\")
                return True

            # Step C (Evaluate/Feedback) - Failure logic
            logger.error(f\"❌ Tests failed on attempt {attempt}.\")
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
                logger.debug(\"Loop broken because agent was considered stuck during test phase.\")
                break

        return False

    def _notify_retry_attempt(self, task, attempt, max_attempts):
        \"\"\"Print and post a comment about the retry status.\"\"\"
        logger.info(f\"🔄 Attempt {attempt}/{max_attempts}...\")
        self._post_github_comment(
            task, f\"🛠️ Attempt {attempt}/{max_attempts} failed. Retrying...\"
        )

    def _execute_opencode_agent(self, ctx, repo_dir):
        \"\"\"Run the Opencode agent command and return any stderr/error content.\"\"\"
        logger.info(\"🤖 Running Opencode agent...\")
        opencode_cmd = [\"opencode\", \"run\", \"--model\", config.model, ctx]
        logger.debug(f\"Executing Agent Command: {' '.join(opencode_cmd)}\")
        _, err = run_command(
            opencode_cmd,
            cwd=repo_dir,
            timeout=config.opencode_run_timeout,
            truncate_lines=50,
        )
        return err

    def _execute_tests(self, repo_dir):
        \"\"\"Run the configured test suite command and return any stderr/error content.\"\"\"
        logger.info(f\"🧪 Running tests: {config.test_command}\")
        logger.debug(f\"Executing Test Command: {config.test_command} in {repo_dir}\")
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
        \"\"\"Process an execution/test error, check if the agent is stuck, and update state.\"\"\"
        snip = error_handler.truncate_output(err, lines=15)
        logger.debug(f\"Error snippet for failure analysis: {snip}\")

        post_attempt_status, _ = run_command(
            [\"git\", \"status\", \"--porcelain\"], cwd=info.repo_dir
        )
        made_changes = post_attempt_status != info.pre_attempt_status
        logger.debug(f\"Changes detected after failure: {made_changes}\")

        summary = error_handler.get_error_summary(snip)
        cleaned_snip = error_handler.clean_snippet(snip)

        is_loop = error_handler.check_error_loop(summary, cleaned_snip, error_summaries)
        logger.debug(f\"Error loop detection: {is_loop}\")

        if not is_loop:
            error_summaries.append((summary, cleaned_snip))

        is_stuck = (
            is_loop
            or error_handler.is_stuck(snip, state.last_err_snip)
            or (info.attempt > 1 and not made_changes)
        )
        logger.debug(f\"Is agent stuck? {is_stuck}\")

        state.consecutive_errs = state.consecutive_errs + 1 if is_stuck else 1
        state.last_err_snip = snip
        logger.debug(f\"Consecutive errors count: {state.consecutive_errs}\")

        if state.consecutive_errs >= 2:
            logger.error(
                \"🚨 Agent stuck! Loop detected or same error twice. Breaking loop.\"
            )
            self.db.fail_task(info.task_id, err)
            return True

        state.ctx += \"\\nThe previous attempt failed with the following errors:\"
        state.ctx += f\"\\n{err}\\nPlease fix these issues and try again.\"
        # Note: self.db.fail_task is called at the end of the loop or when failing task in engine, 
        # but here it's used to mark as failed if stuck.

        return False
