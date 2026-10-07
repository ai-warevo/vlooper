"""Worker module to execute tasks via OpenCode."""

import shlex
from dataclasses import dataclass

from vlooper.config import config
from vlooper.database import Database
from vlooper.exceptions import VLooperError
from vlooper.utils import run_command

from vlooper.processing import error_handler
from vlooper.git import manager as git_manager
from vlooper.github import interaction


@dataclass
class LoopState:
    """Контейнер для отслеживания состояния цикла Opencode."""

    ctx: str
    last_err_snip: str | None = None
    consecutive_errs: int = 0


@dataclass
class AttemptInfo:
    """TODO REPLACE_ME"""

    task_id: str
    attempt: int
    pre_attempt_status: str
    repo_dir: str


class Worker:  # pylint: disable=too-few-public-methods
    """Worker to handle task execution and GitHub interactions."""

    def __init__(self, db: Database):
        """Initialize the worker with a database instance."""
        self.db = db

    def _post_github_comment(self, task, message):
        """Helper to post a comment to the respective GitHub issue or PR."""
        interaction.post_github_comment(task, message)

    def _get_github_author(self, task):
        """Fetch the author of the issue/PR to mention them."""
        return interaction.get_github_author(task)

    def process_next_task(self):
        """Process the next pending task from the database."""
        tasks = self.db.get_pending_tasks()
        if not tasks:
            return False

        # Pick the first pending task
        task = tasks[0]
        task_id = task["id"]

        print(
            f"🛠 Picking up task #{task_id}: {task['task_type']} in "
            f"{task['repo_full_name']} (branch: {task['branch_name']})"
        )

        if not self.db.claim_task(task_id):
            return False  # Someone else claimed it

        # Post 'Started' comment
        self._post_github_comment(task, "🤖 vLooper has picked up this task.")

        try:
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
                print(f"✅ Task #{task_id} completed successfully.")
            else:
                raise VLooperError("Task execution failed (see logs).")
        except Exception as e:  # noqa: W0718
            error_msg = str(e)
            print(f"❌ Task #{task_id} failed: {error_msg}")
            self.db.fail_task(task_id, error_msg)

            if self._is_terminal_failure(task_id):
                print(f"📢 Task #{task_id} reached terminal failure. Escalating...")
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
            success = self._run_opencode_loop(task, task_id, context, repo_dir)
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
                        print(f"⚠️ Could not retrieve PR details: {e}")
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

    def _truncate_output(self, output: str, lines: int = 50) -> str:
        return error_handler.truncate_output(output, lines)

    def _clean_snippet(self, snippet: str) -> str:
        return error_handler.clean_snippet(snippet)

    def _get_error_summary(self, err_text: str) -> str:
        return error_handler.get_error_summary(err_text)

    def _is_stuck(self, new_snip: str, last_err_snip: str | None) -> bool:
        return error_handler.is_stuck(new_snip, last_err_snip)

    def _ask_llm_if_stuck(self, new_snip: str, last_err_snip: str) -> bool | None:
        return error_handler.ask_llm_if_stuck(new_snip, last_err_snip)

    def _build_stuck_prompt(self, new_snip: str, last_err_snip: str) -> str:
        return error_handler.build_stuck_prompt(new_snip, last_err_snip)

    def _parse_llm_stuck_response(self, stdout: str) -> bool | None:
        return error_handler.parse_llm_stuck_response(stdout)

    def _run_opencode_loop(self, task, task_id, ctx, repo_dir):
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

    def _check_error_loop(self, summary, cleaned_snip, error_summaries):
        return error_handler.check_error_loop(summary, cleaned_snip, error_summaries)

    def _handle_attempt_failure(
        self,
        err,
        info: AttemptInfo,
        error_summaries,
        state: LoopState,
    ):
        """Process an execution/test error, check if the agent is stuck, and update state."""
        snip = self._truncate_output(err, lines=15)
        post_attempt_status, _ = run_command(
            ["git", "status", "--porcelain"], cwd=info.repo_dir
        )
        made_changes = post_attempt_status != info.pre_attempt_status

        summary = self._get_error_summary(snip)
        cleaned_snip = self._clean_snippet(snip)

        is_loop = self._check_error_loop(summary, cleaned_snip, error_summaries)
        if not is_loop:
            error_summaries.append((summary, cleaned_snip))

        is_stuck = (
            is_loop
            or self._is_stuck(snip, state.last_err_snip)
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
