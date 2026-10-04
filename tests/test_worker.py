import pytest
import os
import json
import shlex
import sqlite3
from vlooper.config import config
from vlooper.database import Database

@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))

@pytest.fixture
def worker(db):
    return Worker(db)

def test_worker_process_next_task_success(worker, db, monkeypatch, tmp_path):
    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "issue-123")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']

    # Mock config values to use local temp paths
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr(config, "max_retries", 1)
    monkeypatch.setattr(config, "execution_timeout", 5)

    def side_effect_run(cmd, cwd=None, timeout=None):
        cmd_str = " ".join(cmd)
        if "gh repo clone" in cmd_str:
            return "success", None
        if any(x in cmd_str for x in ["git checkout", "git pull", "git checkout -B"]):
            return "", None
        if "opencode run" in cmd_str:
            return "it worked", None
        if any(x in cmd_str for x in ["git commit", "git push", "gh pr create"]):
            return "", None
        return "", None

    with patch("vlooper.worker.run_command", side_effect=side_effect_run), \
         patch.object(Worker, "_get_context", return_value="test context"):
        
        success = worker.process_next_task()
        assert success is True

    # Verify DB status
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row['status'] == "COMPLETED"

def test_worker_process_next_task_failure_and_retry(worker, db, monkeypatch, tmp_path):
    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "issue-123")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']

    monkeypatch.setattr(config, "max_retries", 2)
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))

    def side_effect_run(cmd, cwd=None, timeout=None):
        cmd_str = " ".join(cmd)
        if "opencode run" in cmd_str:
            return None, "Agent failed"
        # Everything else succeeds for the setup part (clone/git)
        return "", None

    with patch("vlooper.worker.run_command", side_effect=side_effect_run), \
         patch.object(Worker, "_get_context", return_value="test context"):
        
        # The task will fail after all retries
        success = worker.process_next_task()
        assert success is False

    # Verify DB status is FAILED
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status, retries FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row['status'] == "FAILED"
        assert row['retries'] >= 2

def test_get_context_issue(worker, db, monkeypatch):
    task = {
        'task_type': 'ISSUE',
        'branch_name': 'issue-1',
        'repo_full_name': 'org/repo'
    }

    mock_view_json = json.dumps({
        "title": "My Issue",
        "body": "Description text"
    })
    mock_comments_json = json.dumps({
        "comments": [{"author": {"login": "user1"}, "body": "comment 1"}]
    })

    def mock_run(cmd, capture_output=True, text=True):
        cmd_str = " ".join(cmd)
        if "gh issue view" in cmd_str and "--json title,body" in cmd_str:
            return mock_view_json, None
        if "gh issue view" in cmd_str and "--json comments" in cmd_str:
            return mock_comments_json, None
        return "", None

    with patch("vlooper.worker.run_command", side_effect=mock_run):
        context = worker._get_context(task, "org/repo")
        assert context is not None
        assert "My Issue" in context
        assert "Description text" in context
        assert "user1" in context
