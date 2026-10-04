import pytest
import sqlite3
from vlooper.database import Database
from vlooper.config import config
import os

@pytest.fixture
def db(tmp_path):
    # Use a temporary file for database testing to ensure isolation and persistence within the test session
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))

def test_db_init(db):
    # Verify table creation by attempting a query
    with db._get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        assert cursor.fetchone() is not None

def test_add_task(db):
    # Test adding new tasks
    assert db.add_task("ISSUE", "org/repo1", "issue-123") is True
    assert db.add_task("PR", "org/repo1", "feature-branch") is True
    # Test duplicate prevention
    assert db.add_task("ISSUE", "org/repo1", "issue-123") is False

def test_get_pending_tasks(db):
    db.add_task("ISSUE", "org/repo1", "issue-1")
    db.add_task("PR", "org/repo2", "branch-2")
    db.add_task("ISSUE", "org/repo3", "issue-3") # This will be PENDING

    pending = db.get_pending_tasks()
    assert len(pending) == 3
    assert pending[0]['repo_full_name'] == "org/repo1"

def test_claim_task(db):
    db.add_task("ISSUE", "org/repo1", "issue-1")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']

    # Successful claim
    assert db.claim_task(task_id) is True
    
    # Check status updated
    with db._get_connection() as conn:
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row[0] == "CLAIMED"

    # Attempt to claim already claimed task should fail
    assert db.claim_task(task_id) is False

def test_complete_task(db):
    db.add_task("ISSUE", "org/repo1", "issue-1")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']
    db.claim_task(task_id)

    db.complete_task(task_id)
    with db._get_connection() as conn:
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row[0] == "COMPLETED"

def test_fail_task_retry(db, monkeypatch):
    # Mock config for max_retries
    monkeypatch.setattr(config, "max_retries", 2)
    
    db.add_task("ISSUE", "org/repo1", "issue-1")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']

    # First failure: should move back to PENDING
    db.fail_task(task_id, "Error 1")
    with db._get_connection() as conn:
        row = conn.execute("SELECT status, retries FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row[0] == "PENDING"
        assert row[1] == 1

    # Second failure: should move back to PENDING
    db.fail_task(task_id, "Error 2")
    with db._get_connection() as conn:
        row = conn.execute("SELECT status, retries FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row[0] == "PENDING"
        assert row[1] == 2

    # Third failure: exceeds max_retries (2), should move to FAILED
    db.fail_task(task_id, "Error 3")
    with db._get_connection() as conn:
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row[0] == "FAILED"

def test_get_active_claimed_task(db):
    db.add_task("ISSUE", "org/repo1", "issue-1")
    tasks = db.get_pending_tasks()
    task_id = tasks[0]['id']
    db.claim_task(task_id)

    active = db.get_active_claimed_task()
    assert active is not None
    assert active['id'] == task_id

def test_task_exists(db):
    db.add_task("ISSUE", "org/repo1", "issue-1")
    assert db.task_exists("org/repo1", "issue-1") is True
    assert db.task_exists("org/repo1", "non-existent") is False
