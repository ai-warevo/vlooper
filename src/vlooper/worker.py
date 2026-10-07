"""Worker module to execute tasks via OpenCode."""

import os
import shlex

from vlooper.config import config
from vlooper.database import Database
from vlooper.exceptions import VLooperError
from vlooper.github_client import create_pull_request, get_issue_details, get_pr_details
from vlooper.utils import build_gh_view_cmd, run_command


class Worker:  # pylint: disable=too-few-public-methods
    """Worker to handle task execution and GitHub interactions."""

    def __init__(self, db: Database):
        """Initialize the worker with a database instance."""
        self.db = db

    def _post_github_comment(self, task, message):
        """Helper to post a comment to the respective GitHub issue or PR."""
        repo_full_name = task["repo_full_name"]
        task_type = task["task_type"]
        branch_name = task["branch_name"]

        if task_type == "ISSUE":
            try:
                # Extracting number from branch name like 'issue-123'
                parts = branch_name.split("-")
                if len(parts) >= 2:
                    num = parts[-1]
                    comment_cmd = [
                        "gh",
                        "issue",
                        "comment",
                        str(num),
                        "--repo",
                        repo_full_name,
                        "--body",
                        message,
                    ]
                    _, err = run_command(comment_cmd)
                    if err:
                        print(f"⚠️ Failed to post GitHub comment for #{num}: {err}")
                else:
                    print(
                        f"⚠️ Could not find issue number in branch name: {branch_name}"
                    )
            except Exception as e:  # noqa: W0718
                print(f"⚠️ Error posting GitHub comment: {e}")
        elif task_type == "PR":
            # For PRs, this is handled by different logic or requires more state.
            pass

    def _get_github_author(self, task):
        """Fetch the author of the issue/PR to mention them."""
        repo_full_name = task["repo_full_name"]
        if task["task_type"] == "ISSUE":
            num = self._get_issue_number(task)
            if num != "unknown" and num:
                cmd = build_gh_view_cmd(
                    "issue", num, repo_full_name, ["author", "--jq", ".author.login"]
                )
                stdout, err = run_command(cmd)
                if not err and stdout:
                    return stdout
        return "assignee"

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
                        details = get_pr_details(repo_full_name, branch_name)
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
        base_dir = os.path.expanduser(config.workspace_base_dir)
        os.makedirs(base_dir, exist_ok=True)
        repo_dir = os.path.join(base_dir, repo_short_name)

        if not os.path.exists(repo_dir):
            print(f"📦 Cloning repository {repo_full_name}...")
            _, err = run_command(
                ["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir
            )
            if err:
                raise VLooperError(err)

        print("🧹 Resetting to default branch...")
        base_branch = "main"
        for b in ["main", "master"]:
            _, err = run_command(["git", "rev-parse", "--verify", b], cwd=repo_dir)
            if not err:
                base_branch = b
                break

        _, err = run_command(
            ["git", "checkout", "-f", base_branch],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)

        _, err = run_command(
            ["git", "pull", "origin", base_branch],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            print(f"⚠️ Could not pull origin {base_branch}, proceeding anyway.")
        return repo_dir

    def _setup_branch(self, repo_dir, branch_name, task_type):
        print(f"🌿 Preparing branch {branch_name}...")
        _, err = run_command(
            ["git", "checkout", "-B", branch_name],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)

        if task_type == "PR":
            print(f"📥 Pulling remote branch {branch_name}...")
            _, err = run_command(
                ["git", "pull", "origin", branch_name],
                cwd=repo_dir,
                timeout=config.execution_timeout,
            )
            if err:
                raise VLooperError(err)
        return True

    def _truncate_output(self, output: str, lines: int = 50) -> str:
        """Truncate output to the last N lines."""
        if not output:
            return ""
        output_lines = output.splitlines()
        if len(output_lines) > lines:
            return "\n".join(output_lines[-lines:])
        return output

    def _run_opencode_loop(self, task, task_id, context, repo_dir):
        """Run the agent-driven loop: Write -> Test -> Fix."""
        ctx = context
        success = False
        last_err_snip = None
        consecutive_errs = 0
        max_attempts = config.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                print(f"🔄 Attempt {attempt}/{max_attempts}...")
                self._post_github_comment(
                    task, f"🛠️ Attempt {attempt}/{max_attempts} failed. Retrying..."
                )

            # 1. Run Opencode (Agent execution) - Requirement 4: opencode_run_timeout
            print("🤖 Running Opencode agent...")
            opencode_cmd = ["opencode", "run", "--model", config.model, ctx]
            _, err = run_command(
                opencode_cmd,
                cwd=repo_dir,
                timeout=config.opencode_run_timeout,
                truncate_lines=50,
            )

            if err:
                print(f"⚠️ Opencode error on attempt {attempt}: {err}")
                snip = self._truncate_output(err, lines=15)
                consecutive_errs = consecutive_errs + 1 if snip == last_err_snip else 1
                last_err_snip = snip

                if consecutive_errs >= 2:
                    print("🚨 Agent stuck! Same error twice. Breaking loop.")
                    self.db.fail_task(task_id, err)
                    break

                ctx += "\nThe previous attempt failed with the following errors:"
                ctx += f"\n{err}\nPlease fix these issues and try again."
                self.db.fail_task(task_id, err)
                continue

            # 2. Run Tests - Requirement 4: test_run_timeout
            print(f"🧪 Running tests: {config.test_command}")
            _, test_err = run_command(
                shlex.split(config.test_command),
                cwd=repo_dir,
                timeout=config.test_run_timeout,
                truncate_lines=50,
            )

            if test_err is None:
                print(f"🎉 Tests passed on attempt {attempt}!")
                return True

            # Step C (Evaluate/Feedback) - Failure logic
            print(f"❌ Tests failed on attempt {attempt}.")
            snip = self._truncate_output(test_err, lines=15)
            consecutive_errs = consecutive_errs + 1 if snip == last_err_snip else 1
            last_err_snip = snip

            if consecutive_errs >= 2:
                print("🚨 Agent stuck! Same error twice. Breaking loop.")
                self.db.fail_task(task_id, test_err)
                break

            ctx += "\nThe previous attempt failed with the following errors:"
            ctx += f"\n{test_err}\nPlease fix these issues and try again."
            self.db.fail_task(task_id, test_err)

        return success

    def _commit_and_push(self, repo_dir, branch_name, commit_msg):
        print("💾 Committing changes...")
        commit_cmd = [
            "git",
            "-c",
            f"user.name={config.git_user_name}",
            "-c",
            f"user.email={config.git_user_email}",
            "commit",
            "-am",
            commit_msg,
        ]
        _, err = run_command(commit_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err:
            raise VLooperError(err)

        print("📤 Pushing to origin...")
        push_cmd = ["git", "push", "origin", branch_name]
        _, err = run_command(push_cmd, cwd=repo_dir, timeout=config.execution_timeout)
        if err:
            raise VLooperError(err)
        return True

    def _create_pr(self, repo_full_name, repo_dir, branch_name):
        print("📢 Creating Pull Request...")
        _, err = create_pull_request(
            repo_full_name,
            f"Fix for {branch_name}",
            "Automated fix by vLooper agent.",
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)

        details = get_pr_details(repo_full_name, branch_name)
        if details:
            return details[0]
        return None

    def _stash_and_checkout_main(self, repo_dir):
        """Stash changes and checkout default branch if a push or PR creation fails."""
        print("🧹 Stashing changes and checking out default branch...")
        run_command(["git", "stash"], cwd=repo_dir)
        base_branch = "main"
        for b in ["main", "master"]:
            _, err = run_command(["git", "checkout", "-f", b], cwd=repo_dir)
            if not err:
                base_branch = b
                break

        _, err = run_command(
            ["git", "checkout", "-f", base_branch],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            print(f"⚠️ Failed to checkout default branch during cleanup: {err}")

    def _delete_local_branch(self, repo_dir, branch_name):
        """Delete the local git branch after work is done."""
        print(f"🗑 Deleting local branch {branch_name}...")
        # 1. Forcefully clean up any uncommitted changes
        # or untracked files to allow switching branches.
        run_command(["git", "reset", "--hard", "HEAD"], cwd=repo_dir)
        run_command(["git", "clean", "-fd"], cwd=repo_dir)

        # 2. Switch back to a default branch (main or master).
        switched = False
        for b in ["main", "master"]:
            _, err = run_command(["git", "checkout", "-f", b], cwd=repo_dir)
            if not err:
                switched = True
                break

        if not switched:
            print("⚠️ Could not checkout main/master, attempting to detach HEAD...")
            _, err = run_command(["git", "checkout", "--detach"], cwd=repo_dir)
            if not err:
                switched = True

        # 3. Delete the branch.
        _, err = run_command(["git", "branch", "-D", branch_name], cwd=repo_dir)
        if err:
            print(f"ℹ️ Note: Could not delete local branch {branch_name}: {err}")

    def _delete_remote_branch(self, repo_dir, branch_name):
        """Attempt to delete the remote git branch."""
        print(f"🗑 Attempting to delete remote branch {branch_name}...")
        _, err = run_command(
            ["git", "push", "origin", "--delete", branch_name], cwd=repo_dir
        )
        if err:
            print(f"ℹ️ Note: Could not delete remote branch {branch_name}: {err}")

    def _get_context(self, task, repo_full_name):
        """Fetch context for the task from GitHub."""
        if task["task_type"] == "ISSUE":
            return self._get_issue_context(task, repo_full_name)
        return self._get_pr_context(task, repo_full_name)

    def _get_issue_context(self, task, repo_full_name):
        num = (
            task["branch_name"].split("-")[-1]
            if "-" in task["branch_name"]
            else "unknown"
        )
        if num == "unknown":
            return None

        details = get_issue_details(num, repo_full_name)
        if not details:
            return None
        title, body, comments_text = details

        return (
            f"Задача #{num} в репозитории {repo_full_name}: {title}\n"
            f"Описание:\n{body}\n\nИстория переписки:\n{comments_text}"
        )

    def _get_pr_context(self, task, repo_full_name):
        try:
            details = get_pr_details(repo_full_name, task["branch_name"])
            if not details:
                return None

            num, _, body, review_text = details

            if "Исправлено ботом" in review_text:
                return None

            return (
                f"Доработка по Pull Request #{num} в репозитории "
                f"{repo_full_name} (ветка {task['branch_name']}).\nЗамечания к коду:\n"
                f"{review_text}\n\nОписание PR:\n{body}"
            )
        except Exception:  # noqa: W0718
            return None

    def _get_issue_number(self, task):
        """Get issue number from task."""
        if task["task_type"] == "ISSUE":
            try:
                return task["branch_name"].split("-")[-1]
            except Exception:  # noqa: W0718
                return "unknown"
        return "PR"
