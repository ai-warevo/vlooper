"""Worker module to execute tasks via OpenCode."""

import os
import shlex

from vlooper.config import config
from vlooper.database import Database
from vlooper.exceptions import VLooperError
from vlooper.github_client import create_pull_request, get_issue_details, get_pr_details
from vlooper.utils import run_command


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
            success = self._execute_task(task, task_id)
            if success:
                self.db.complete_task(task_id)
                # Post finishing comment (for issues)
                self._post_github_comment(task, "✅ Task completed successfully!")
                print(f"✅ Task #{task_id} completed successfully.")
            else:
                raise VLooperError("Task execution failed (see logs).")
        except Exception as e:  # noqa: W0718
            error_msg = str(e)
            print(f"❌ Task #{task_id} failed: {error_msg}")
            self.db.fail_task(task_id, error_msg)
            return False

        return True

    def _execute_task(self, task, task_id):
        """Execute the task details."""
        repo_full_name = task["repo_full_name"]
        branch_name = task["branch_name"]
        task_type = task["task_type"]
        repo_short_name = repo_full_name.split("/")[-1]

        context = self._get_context(task, repo_full_name)
        if not context:
            return False

        commit_msg = self._generate_commit_message(task, branch_name)

        # 1 & 2 & 3. Setup workspace and branch
        repo_dir = self._prepare_repo_dir(repo_full_name, repo_short_name)
        if not repo_dir:
            return False

        if not self._setup_branch(repo_dir, branch_name, task_type):
            return False

        # 4. Run Opencode Loop
        success = self._run_opencode_loop(task, task_id, context, repo_dir)
        if not success:
            raise VLooperError(f"Task failed after {config.max_retries} retries.")

        # 5. Commit and Push
        if not self._commit_and_push(repo_dir, branch_name, commit_msg):
            return False

        # 6. Create PR if it was an issue
        if task_type == "ISSUE":
            self._create_pr(repo_full_name, repo_dir, branch_name)

        return True

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

        print("🧹 Resetting to main...")
        _, err = run_command(
            ["git", "checkout", "main"], cwd=repo_dir, timeout=config.execution_timeout
        )
        if err:
            raise VLooperError(err)

        _, err = run_command(
            ["git", "pull", "origin", "main"],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            print("⚠️ Could not pull origin main, proceeding anyway.")
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

    def _run_opencode_loop(self, task, task_id, context, repo_dir):
        current_context = context
        success = False

        for attempt in range(config.max_retries + 1):
            if attempt > 0:
                print(f"🔄 Attempt {attempt}/{config.max_retries}...")
                self._post_github_comment(
                    task,
                    f"🛠️ Attempt {attempt}/{config.max_retries} failed. Retrying...",
                )

            opencode_cmd = [
                "opencode",
                "run",
                "--model",
                config.model,
                "--prompt",
                current_context,
            ]
            _, err = run_command(
                opencode_cmd, cwd=repo_dir, timeout=config.execution_timeout
            )
            if err:
                print(f"⚠️ Opencode error on attempt {attempt}: {err}")
                current_context += (
                    f"\nThe previous attempt failed with the following errors:\n{err}"
                    "\nPlease fix these issues and try again."
                )
                self.db.fail_task(task_id, err)
                continue

            test_cmd = shlex.split(config.test_command)
            print(f"🧪 Running tests: {config.test_command}")
            _, test_err = run_command(
                test_cmd, cwd=repo_dir, timeout=config.execution_timeout
            )

            if test_err is None:
                print(f"🎉 Tests passed on attempt {attempt}!")
                success = True
                break

            # Step C (Evaluate/Feedback) - Failure
            print(f"❌ Tests failed on attempt {attempt}.")
            current_context += (
                f"\nThe previous attempt failed with the following errors:\n{test_err}"
                "\nPlease fix these issues and try again."
            )
            self.db.fail_task(task_id, test_err)

        return success

    def _commit_and_push(self, repo_dir, branch_name, commit_msg):
        print("💾 Committing changes...")
        commit_cmd = [
            "git",
            "-c",
            "user.name=AI OpenCode Bot",
            "-c",
            "user.email=ai-bot@://github.com",
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
