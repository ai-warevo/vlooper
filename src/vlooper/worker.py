"""Worker module to execute tasks via OpenCode."""
import json
import os
import shlex
import subprocess

from vlooper.config import config
from vlooper.database import Database
from vlooper.exceptions import VLooperError


def run_command(cmd, cwd=None, timeout=None):
    """Run a command with an optional timeout."""
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, check=False
        )
        if res.returncode != 0:
            error_msg = (
                f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\n"
                f"STDERR:\n{res.stderr}"
            )
            return None, error_msg
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = e.stderr.decode() if e.stderr else ""
        error_msg = (
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        return None, error_msg
    except Exception as e:  # noqa: BLE001
        return None, str(e)


class Worker:
    """Worker to handle task execution and GitHub interactions."""

    def __init__(self, db: Database):
        """Initialize the worker with a database instance."""
        self.db = db

    def _post_github_comment(self, task, message):
        """Helper to post a comment to the respective GitHub issue or PR."""
        repo_full_name = task["repo_full_name"]

        if task["task_type"] == "ISSUE":
            try:
                # Extracting number from branch name like 'issue-123'
                parts = task["branch_name"].split("-")
                if len(parts) >= 2:
                    num = parts[-1]
                else:
                    return  # Skip if we can't find human-readable issue number in branch
            except Exception:  # noqa: BLE001
                return
        else:
            # For PRs, this is handled by different logic or requires more state.
            # Providing a fallback mechanism.
            return

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
        _stdout, err = run_command(comment_cmd)
        if err:
            print(f"⚠️ Failed to post GitHub comment for #{num}: {err}")

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
        except Exception as e:  # noqa: BLE001
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

        # Extract repo short name
        repo_short_name = repo_full_name.split("/")[-1]

        # Get context for the AI agent
        context = self._get_context(task, repo_full_name)
        if not context:
            return False

        commit_msg = (
            f"{'refactor: ' if task_type == 'PR' else 'fix: '} "
            f"#{self._get_issue_number(task)}"
        )
        if task_type == "ISSUE":
            try:
                num = branch_name.split("-")[-1]
                commit_msg = f"fix #{num}"
            except Exception:  # noqa: BLE001
                commit_msg = "fix issue"
        else:
            commit_msg = f"refactor PR on {branch_name}"

        # 1. Setup workspace
        base_dir = os.path.expanduser(config.workspace_base_dir)
        os.makedirs(base_dir, exist_ok=True)
        repo_dir = os.path.join(base_dir, repo_short_name)

        if not os.path.exists(repo_dir):
            print(f"📦 Cloning repository {repo_full_name}...")
            _stdout, err = run_command(
                ["gh", "repo", "clone", repo_full_name, repo_short_name], cwd=base_dir
            )
            if err:
                raise VLooperError(err)

        # 2. Reset to main and update
        print("🧹 Resetting to main...")
        _stdout, err = run_command(
            ["git", "checkout", "main"], cwd=repo_dir, timeout=config.execution_timeout
        )
        if err:
            raise VLooperError(err)

        _stdout, err = run_command(
            ["git", "pull", "origin", "main"],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            print("⚠️ Could not pull origin main, proceeding anyway.")

        # 3. Checkout/Create task branch
        print(f"🌿 Preparing branch {branch_name}...")
        _stdout, err = run_command(
            ["git", "checkout", "-B", branch_name],
            cwd=repo_dir,
            timeout=config.execution_timeout,
        )
        if err:
            raise VLooperError(err)

        if task_type == "PR":
            print(f"📥 Pulling remote branch {branch_name}...")
            _stdout, err = run_command(
                ["git", "pull", "origin", branch_name],
                cwd=repo_dir,
                timeout=config.execution_timeout,
            )
            if err:
                raise VLooperError(err)

        # 4. Run Opencode with Hardcore Loop
        print("🚀 Running OpenCode with Hardcore Loop...")
        current_context = context
        success = False

        for attempt in range(config.max_retries + 1):
            if attempt > 0:
                print(f"🔄 Attempt {attempt}/{config.max_retries}...")
                # Post failure comment on retry
                self._post_github_comment(
                    task,
                    f"🛠️ Attempt {attempt}/{config.max_retries} failed. Retrying...",
                )

            # Step A (Generate)
            opencode_cmd = [
                "opencode",
                "run",
                "--model",
                config.model,
                "--prompt",
                current_context,
            ]
            _stdout, err = run_command(
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

            # Step B (Verify)
            test_cmd = shlex.split(config.test_command)
            print(f"🧪 Running tests: {config.test_command}")
            _test_stdout, test_err = run_command(
                test_cmd, cwd=repo_dir, timeout=config.execution_timeout
            )

            if test_err is None:
                # Step C (Evaluate/Feedback) - Success
                print(f"🎉 Tests passed on attempt {attempt}!")
                success = True
                break
            else:
                # Step C (Evaluate/Feedback) - Failure
                print(f"❌ Tests failed on attempt {attempt}.")
                current_context += (
                    f"\nThe previous attempt failed with the following errors:\n{test_err}"
                    "\nPlease fix these issues and try again."
                )
                self.db.fail_task(task_id, test_err)

        if not success:
            raise VLooperError(f"Task failed after {config.max_retries} retries.")

        # 5. Commit and Push
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
        _stdout, err = run_command(
            commit_cmd, cwd=repo_dir, timeout=config.execution_timeout
        )
        if err:
            raise VLooperError(err)

        print("📤 Pushing to origin...")
        push_cmd = ["git", "push", "origin", branch_name]
        _stdout, err = run_command(
            push_cmd, cwd=repo_dir, timeout=config.execution_timeout
        )
        if err:
            raise VLooperError(err)

        # 6. Create PR if it was an issue
        if task_type == "ISSUE":
            print("📢 Creating Pull Request...")
            pr_create_cmd = [
                "gh",
                "pr",
                "create",
                "--repo",
                repo_full_name,
                "--title",
                f"Fix for {branch_name}",
                "--body",
                "Automated fix by vLooper agent.",
            ]
            _stdout, err = run_command(
                pr_create_cmd, cwd=repo_dir, timeout=config.execution_timeout
            )
            if err:
                raise VLooperError(err)

        return True

    def _get_context(self, task, repo_full_name):
        """Fetch context for the task from GitHub."""
        num = (
            task["branch_name"].split("-")[-1] if task["task_type"] == "ISSUE" else None
        )

        if task["task_type"] == "ISSUE":
            try:
                view_cmd = [
                    "gh",
                    "issue",
                    "view",
                    str(num),
                    "--repo",
                    repo_full_name,
                    "--json",
                    "title,body",
                ]
                res, err = run_command(view_cmd)
                if err:
                    return None
                issue_data = json.loads(res)
                title = issue_data["title"]
                body = issue_data["body"] or ""

                comments_cmd = [
                    "gh",
                    "issue",
                    "view",
                    str(num),
                    "--repo",
                    repo_full_name,
                    "--json",
                    "comments",
                ]
                res_c, err_c = run_command(comments_cmd)
                if err_c:
                    comments_text = ""
                else:
                    comments = json.loads(res_c).get("comments", [])
                    comments_text = "\n".join(
                        [
                            f"Комментарий от {c['author']['login']}: {c['body']}"
                            for c in comments
                        ]
                    )

                return (
                    f"Задача #{num} в репозитории {repo_full_name}: {title}\n"
                    f"Описание:\n{body}\n\nИстория переписки:\n{comments_text}"
                )
            except Exception as e:  # noqa: BLE001
                print(f"Error getting issue context: {e}")
                return None
        else:  # PR
            try:
                branch = task["branch_name"]
                list_pr_cmd = [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    repo_full_name,
                    "--head",
                    branch,
                    "--json",
                    "number,title,body,comments,reviews",
                ]
                res_p, err_p = run_command(list_pr_cmd)
                if err_p or not res_p:
                    return None
                prs = json.loads(res_p)
                if not prs:
                    return None
                pr = prs[0]

                num = pr["number"]
                title = pr["title"]
                body = pr["body"] or ""

                review_text = ""
                for r in pr.get("reviews", []):
                    if r.get("body"):
                        review_text += f"Ревью от {r['author']['login']}: {r['body']}\n"
                for c in pr.get("comments", []):
                    review_text += f"Замечание от {c['author']['login']}: {c['body']}\n"

                if "Исправлено ботом" in review_text:
                    return None

                return (
                    f"Доработка по Pull Request #{num} в репозитории "
                    f"{repo_full_name} (ветка {branch}).\nЗамечания к коду:\n"
                    f"{review_text}\n\nОписание PR:\n{body}"
                )
            except Exception as e:  # noqa: BLE001
                print(f"Error getting PR context: {e}")
                return None

    def _get_issue_number(self, task):
        """Get issue number from task."""
        if task["task_type"] == "ISSUE":
            try:
                return task["branch_name"].split("-")[-1]
            except Exception:  # noqa: BLE001
                return "unknown"
        return "PR"


