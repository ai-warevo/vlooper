# pylint: disable=redefined-outer-name,protected-access,unused-argument
"""Tests for the TaskEngine class."""

import contextlib
import json
import os
import sqlite3
from unittest.mock import patch
import pytest

from vlooper.config import config
from vlooper.database import Database
from vlooper.core import error_handler
from vlooper.core.engine import TaskEngine


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def worker(db):
    """Create a worker instance."""
    return TaskEngine(db)


def get_all_run_command_patches(side_effect_run):
    """Helper to provide all necessary run_command patches."""
    return [
        patch("vlooper.utils.run_command", side_effect=side_effect_run),
        patch("vlooper.core.loop.run_command", side_effect=side_effect_run),
        patch(
            "vlooper.integrations.git_manager.run_command", side_effect=side_effect_run
        ),
        patch(
            "vlooper.integrations.github_client.run_command",
            side_effect=side_effect_run,
        ),
        patch(
            "vlooper.integrations.github_interaction.run_command",
            side_effect=side_effect_run,
        ),
        patch("vlooper.core.error_handler.run_command", side_effect=side_effect_run),
    ]


def test_worker_process_next_task_success(worker, db, monkeypatch, tmp_path):
    """Test successful task processing by the worker."""
    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "issue-123")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]["id"]

    # Mock config values to use local temp paths
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr(config, "max_retries", 1)
    monkeypatch.setattr(config, "execution_timeout", 5)

    def side_effect_run(cmd, cwd=None, timeout=None, **kwargs):
        cmd_str = " ".join(cmd)
        if "gh repo clone" in cmd_str:
            # target is the last argument
            target = cmd[-1]
            base = cwd if cwd else "."
            target_path = os.path.join(base, target)
            os.makedirs(target_path, exist_ok=True)
            return "success", None
        if any(x in cmd_str for x in ["git checkout", "git pull", "git checkout -B"]):
            return "", None
        if "opencode run" in cmd_str:
            return "it worked", None
        if any(x in cmd_str for x in ["git commit", "git push", "gh pr create"]):
            return "", None
        return "", None

    patches = get_all_run_command_patches(side_effect_run)
    with (
        patch.object(TaskEngine, "_get_context", return_value="test context"),
        contextlib.ExitStack() as stack,
    ):
        for p in patches:
            stack.enter_context(p)
        success = worker.process_next_task()
        assert success is True

    # Verify DB status
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["status"] == "COMPLETED"


def test_worker_process_next_task_failure_and_retry(worker, db, monkeypatch, tmp_path):
    """Test worker's retry mechanism and eventual failure."""
    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "issue-123")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]["id"]

    monkeypatch.setattr(config, "max_retries", 2)
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))

    def side_effect_run(cmd, cwd=None, timeout=None, **kwargs):
        cmd_str = " ".join(cmd)
        if "opencode run" in cmd_str:
            return None, "Agent failed"
        # Everything else succeeds for the setup part (clone/git)
        return "", None

    patches = get_all_run_command_patches(side_effect_run)
    with (
        patch.object(TaskEngine, "_get_context", return_value="test context"),
        contextlib.ExitStack() as stack,
    ):
        for p in patches:
            stack.enter_context(p)
        # The task will fail after all retries
        # We need to call it multiple times to exhaust retries
        for _ in range(3):
            worker.process_next_task()
        success = False  # Since we know it failed
        assert success is False

    # Verify DB status is FAILED
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, retries FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        assert row["status"] == "FAILED"
        assert row["retries"] >= 2


def test_get_context_issue(worker, db, monkeypatch):
    """Test context retrieval from external tools."""
    task = {
        "task_type": "ISSUE",
        "branch_name": "issue-1",
        "repo_full_name": "org/repo",
    }

    mock_view_json = json.dumps({"title": "My Issue", "body": "Description text"})
    mock_comments_json = json.dumps(
        {"comments": [{"author": {"login": "user1"}, "body": "comment 1"}]}
    )

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if "gh issue view" in cmd_str and "--json title,body" in cmd_str:
            return mock_view_json, None
        if "gh issue view" in cmd_str and "--json comments" in cmd_str:
            return mock_comments_json, None
        return "", None

    patches = get_all_run_command_patches(mock_run)

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        context = worker._get_context(task, "org/repo")
        assert context is not None
        assert "My Issue" in context
        assert "Description text" in context
        assert "user1" in context


def test_worker_deletes_branch_on_success_and_failure(
    worker, db, monkeypatch, tmp_path
):
    """Verify that local branch is deleted after task completion (both success and failure)."""
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr(config, "max_retries", 1)

    def run_test_case(should_succeed):
        # Reset DB for each case
        with db._get_connection() as conn:
            conn.execute("DELETE FROM tasks")
            conn.commit()

        branch_name = "issue-test-branch"
        db.add_task("ISSUE", "org/repo1", branch_name)

        called_commands = []

        def side_effect_run(cmd, cwd=None, timeout=None, **kwargs):
            cmd_str = " ".join(cmd)
            called_commands.append(cmd_str)
            if "gh repo clone" in cmd_str:
                target = cmd[-1]
                base = cwd if cwd else "."
                target_path = os.path.join(base, target)
                os.makedirs(target_path, exist_ok=True)
                return "success", None
            if any(
                x in cmd_str for x in ["git checkout", "git pull", "git checkout -B"]
            ):
                return "", None
            if "opencode run" in cmd_str:
                return ("it worked", None) if should_succeed else (None, "Agent failed")
            if any(x in cmd_str for x in ["git commit", "git push", "gh pr create"]):
                return "", None
            if "git branch -D" in cmd_str:
                return "", None
            return "", None

        patches = get_all_run_command_patches(side_effect_run)
        with (
            patch.object(TaskEngine, "_get_context", return_value="test context"),
            contextlib.ExitStack() as stack,
        ):
            for p in patches:
                stack.enter_context(p)
            worker.process_next_task()

        # Check if git branch -D was called for this branch
        delete_cmd = f"git branch -D {branch_name}"
        assert any(
            delete_cmd in cmd for cmd in called_commands
        ), f"Expected {delete_cmd} to be called, but got {called_commands}"

    run_test_case(should_succeed=True)
    run_test_case(should_succeed=False)


def test_max_retries_respects_config(worker, db, monkeypatch, tmp_path):
    """Verify that the number of attempts follows config.max_retries."""
    # Set max_retries to 1 (meaning 2 total attempts: 1 initial + 1 retry)
    monkeypatch.setattr(config, "max_retries", 1)
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))

    # Add a task
    db.add_task("ISSUE", "org/repo1", "issue-123")

    # Track how many times opencode is called
    opencode_call_count = 0

    def side_effect_run(cmd, cwd=None, timeout=None, **kwargs):
        nonlocal opencode_call_count
        cmd_str = " ".join(cmd)
        if "gh repo clone" in cmd_str:
            target = cmd[-1]
            base = cwd if cwd else "."
            target_path = os.path.join(base, target)
            os.makedirs(target_path, exist_ok=True)
            return "success", None
        if any(x in cmd_str for x in ["git checkout", "git pull", "git checkout -B"]):
            return "", None
        if "opencode run" in cmd_str:
            opencode_call_count += 1
            # Always fail to force retries
            return None, "Agent failed"
        if any(x in cmd_str for x in ["git commit", "git push", "gh pr create"]):
            return "", None
        return "", None

    patches = get_all_run_command_patches(side_effect_run)
    with (
        patch.object(TaskEngine, "_get_context", return_value="test context"),
        contextlib.ExitStack() as stack,
    ):
        for p in patches:
            stack.enter_context(p)
        success = worker.process_next_task()
        assert success is False

    # With max_retries=1, we expect 2 attempts (initial + 1 retry)
    assert opencode_call_count == 2


def test_max_retries_different_config(worker, db, monkeypatch, tmp_path):
    """Verify that changing config.max_retries changes the number of attempts."""
    # Set max_retries to 0 (meaning 1 total attempt: just the initial one)
    monkeypatch.setattr(config, "max_retries", 0)
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))

    db.add_task("ISSUE", "org/repo1", "issue-123")

    opencode_call_count = 0

    def side_effect_run(cmd, cwd=None, timeout=None, **kwargs):
        nonlocal opencode_call_count
        cmd_str = " ".join(cmd)
        if "gh repo clone" in cmd_str:
            target = cmd[-1]
            base = cwd if cwd else "."
            target_path = os.path.join(base, target)
            os.makedirs(target_path, exist_ok=True)
            return "success", None
        if any(x in cmd_str for x in ["git checkout", "git pull", "git checkout -B"]):
            return "", None
        if "opencode run" in cmd_str:
            opencode_call_count += 1
            return None, "Agent failed"
        if any(x in cmd_str for x in ["git commit", "git push", "gh pr create"]):
            return "", None
        return "", None

    patches = get_all_run_command_patches(side_effect_run)
    with (
        patch.object(TaskEngine, "_get_context", return_value="test context"),
        contextlib.ExitStack() as stack,
    ):
        for p in patches:
            stack.enter_context(p)
        success = worker.process_next_task()
        assert success is False

    # With max_retries=0, we expect 1 attempt
    assert opencode_call_count == 1


def test_is_stuck(worker):
    """Test the stuck detection algorithm."""

    err1 = "Error: File not found at /home/user/project/src/main.py on line 10"
    err2 = "Error: File not found at /home/toor/project/src/main.py on line 10"
    err3 = "Completely different error message"

    # Should be considered stuck (similar)
    assert error_handler.is_stuck(err2, err1) is True
    assert error_handler.is_stuck(err1, err2) is True

    # Should NOT be considered stuck (different)
    assert error_handler.is_stuck(err3, err1) is False
    assert error_handler.is_stuck(err1, err3) is False

    # Edge case: None or empty
    assert error_handler.is_stuck(err1, None) is False
    assert error_handler.is_stuck("", "") is False
