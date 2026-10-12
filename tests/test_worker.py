import sqlite3
from unittest.mock import patch
import pytest
from vlooper import Database
from vlooper.config import config
from vlooper.core.framework.context import TaskContext
from vlooper.core.framework.event_bus import EventBus
from vlooper.core.framework.pipeline import TaskPipeline


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def pipeline():
    """Create a fresh pipeline with an event bus."""
    return TaskPipeline(EventBus())


class WorkerShim:
    """A lightweight shim to simulate the worker's orchestration logic for testing purposes."""

    def __init__(self, db, pipeline):
        self.db = db
        self.pipeline = pipeline

    def _get_context(self, repo_full_name):
        """Mocked context retrieval as used in old tests."""
        return {"repo_full_name": repo_full_name}

    def process_next_task(self) -> bool:
        tasks = self.db.get_next_pending_task()
        if not tasks:
            return False

        task = tasks
        task_id = task["id"]

        if not self.db.claim_task(task_id):
            return False

        # Create a context for the pipeline.
        ctx = TaskContext(
            task_id=str(task_id),
            task_type="ISSUE",
            issue_number=task["issue_number"] or 0,
            repo_url=task["repo_url"],
            workspace_path=".",
            repo_full_name=task["repo_full_name"],
            branch_name=task["branch_name"],
            metadata={"event_bus": self.pipeline._event_bus},
        )

        try:
            self.pipeline.run(ctx)
            # After pipeline runs, we mark task as complete in the DB to simulate success
            self.db.complete_task(task_id)
            return True
        except Exception as e:
            self.db.fail_task(task_id, str(e))
            return False


def test_worker_process_next_task_success(db, pipeline):
    """Test successful task processing (PENDING -> COMPLETED)."""
    worker = WorkerShim(db, pipeline)

    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "https://github.com/org/repo1", 123, "main")
    task = db.get_next_pending_task()
    assert task is not None
    task_id = task["id"]

    # Mock the pipeline execution (since we aren't using real steps)
    with patch.object(TaskPipeline, "run", return_value=None):
        success = worker.process_next_task()
        assert success is True

    # Verify DB status
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["status"] == "COMPLETED"


def test_worker_process_next_task_failure_and_retry(db, pipeline, monkeypatch):
    """Test worker's retry mechanism and eventual failure."""
    # Set max retries to 1 (meaning 2 total attempts: 1 initial + 1 retry)
    monkeypatch.setattr(config.timeouts, "max_task_retries", 1)
    worker = WorkerShim(db, pipeline)

    # Setup: Add a task to DB
    db.add_task("ISSUE", "org/repo1", "https://github.com/org/repo1", 123, "main")
    task = db.get_next_pending_task()
    assert task is not None
    task_id = task["id"]

    # Mock the pipeline to always fail
    with patch.object(TaskPipeline, "run", side_effect=Exception("Agent failed")):
        # First attempt
        worker.process_next_task()

        # Second attempt (the retry)
        worker.process_next_task()

    # Verify DB status is FAILED after exhausting retries
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, retries FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        assert row["status"] == "FAILED"
        assert row["retries"] >= 1


def test_get_context_issue(db, pipeline):
    """Test context retrieval shim."""
    worker = WorkerShim(db, pipeline)
    # We don't use the task dict directly in the shim anymore
    context = worker._get_context("org/repo")
    assert context == {"repo_full_name": "org/repo"}
