"""Database management for vLooper."""

import sqlite3

from vlooper.config import config


class Database:
    """SQLite database handler for tasks."""

    def __init__(self, db_path=config.db_path):
        """Initialize the database with a given path."""
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Get a connection to the SQLite database."""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL, -- ISSUE or PR
                    repo_full_name TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    status TEXT NOT NULL, -- PENDING, CLAIMED, COMPLETED, FAILED
                    retries INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_task(self, task_type, repo_full_name, branch_name):
        """Add a new task to the database."""
        # Check if task already exists to avoid duplicates
        if self.task_exists(repo_full_name, branch_name):
            return False

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_type, repo_full_name, branch_name, status)
                VALUES (?, ?, ?, 'PENDING')
            """,
                (task_type, repo_full_name, branch_name),
            )
            conn.commit()
        return True

    def get_pending_tasks(self):
        """Retrieve all pending tasks."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE status = 'PENDING'")
            return cursor.fetchall()

    def get_failed_tasks(self, min_age_seconds: int = 0):
        """Retrieve failed tasks from the database that are older than min_age_seconds."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM tasks WHERE status = 'FAILED'"
            params = []
            if min_age_seconds > 0:
                # SQLite datetime comparison
                query += " AND updated_at < datetime('now', ?)"
                params.append(f"-{min_age_seconds} seconds")

            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def get_all_tasks(self):
        """Retrieve all tasks from the database."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks")
            return cursor.fetchall()

    def reset_task_status(self, task_id):
        """Reset a task's status to PENDING and reset its retry count."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'PENDING', retries = 0 WHERE id = ?",
                (task_id,),
            )
            conn.commit()

    def claim_task(self, task_id):
        """Claim a task for processing."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE tasks 
                SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP 
                WHERE id = ? AND (status = 'PENDING' OR (status = 'FAILED' AND retries < ?))
            """,
                (task_id, config.max_retries),
            )
            conn.commit()
            return cursor.rowcount > 0

    def complete_task(self, task_id):
        """Mark a task as completed."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks 
                SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """,
                (task_id,),
            )
            conn.commit()

    def fail_task(self, task_id, error_msg):
        """Mark a task as failed and handle retries."""
        with self._get_connection() as conn:
            # Check retries
            cursor = conn.execute("SELECT retries FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row and row[0] < config.max_retries:
                conn.execute(
                    """
                    UPDATE tasks 
                    SET status = 'PENDING', retries = retries + 1, last_error = ?, \
updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """,
                    (error_msg, task_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE tasks 
                    SET status = 'FAILED', last_error = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """,
                    (error_msg, task_id),
                )
            conn.commit()

    def get_active_claimed_task(self):
        """Get the currently active claimed task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE status = 'CLAIMED'")
            return cursor.fetchone()

    def task_exists(self, repo_full_name, branch_name):
        """Check if a task for a specific repo and branch already exists."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM tasks WHERE repo_full_name = ? AND branch_name = ?",
                (repo_full_name, branch_name),
            )
            return cursor.fetchone() is not None
