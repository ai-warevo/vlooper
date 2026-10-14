"""Database management for vLooper."""

import json
import sqlite3
from typing import Any

from vlooper.config import config
from vlooper.persistence.db_migrator import DBMigrator
from vlooper.persistence.migrations import MIGRATIONS


class Database:
    """SQLite database handler for tasks."""

    def __init__(self, db_path=config.infra.db_path):
        """Initialize the database with a given path."""
        self.db_path = db_path
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations."""
        migrator = DBMigrator(self.db_path)
        migrator.migrate(MIGRATIONS, direction="up")

    def _get_connection(self):
        """Get a connection to the SQLite database."""
        return sqlite3.connect(self.db_path)

    def add_task(self, task_type, repo_full_name, repo_url, issue_number, branch_name, meta: str | None = None) -> int | None:
        """Add a new task to the database. Returns the new task ID or None if it already exists."""
        # Check if task already exists to avoid duplicates
        if self.task_exists(repo_full_name, branch_name):
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (task_type, repo_full_name, repo_url, issue_number, 
                                   branch_name, status, meta)
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
                (task_type, repo_full_name, repo_url, issue_number, branch_name, meta),
            )
            conn.commit()
            return cursor.lastrowid

    def get_next_pending_task(self) -> dict[str, Any] | None:
        """Retrieve a single pending task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE status = 'PENDING' LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

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

    def get_next_failed_task(self, min_age_seconds: int = 0) -> dict[str, Any] | None:
        """Retrieve a single failed task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM tasks WHERE status = 'FAILED'"
            params = []
            if min_age_seconds > 0:
                query += " AND updated_at < datetime('now', ?)"
                params.append(f"-{min_age_seconds} seconds")

            query += " LIMIT 1"
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_tasks(self):
        """Retrieve all tasks from the database."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks")
            return cursor.fetchall()

    def get_task_by_id(self, task_id: int) -> dict[str, Any] | None:
        """Retrieve a single task by its ID."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_step_for_task(self, task_id: int, current_order_index: int) -> dict[str, Any] | None:
        """Retrieve the next step for a given task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks_steps WHERE task_id = ? AND order_index > ? ORDER BY order_index ASC LIMIT 1",
                (task_id, current_order_index),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_step_input_data(self, step_id: int, input_data: dict | None):
        """Update the input data for a specific step."""
        import json
        input_json = json.dumps(input_data) if input_data else None
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tasks_steps SET input_data = ? WHERE id = ?",
                (input_json, step_id),
            )
            conn.commit()

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
                (task_id, config.timeouts.max_task_retries),
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
            if row and row[0] < config.timeouts.max_task_retries:
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

    def add_step(self, task_id: int, role: str, order_index: int, input_data: dict | None = None) -> int:
        """Add a new step to a task."""
        input_json = json.dumps(input_data) if input_data else None
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks_steps (task_id, role, status, order_index, input_data)
                VALUES (?, ?, 'PENDING', ?, ?)
            """,
                (task_id, role, order_index, input_json),
            )
            conn.commit()
            return cursor.lastrowid

    def get_task_steps(self, task_id: int) -> list[dict[str, Any]]:
        """Retrieve all steps for a given task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks_steps WHERE task_id = ? ORDER BY order_index ASC", (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_completed_steps_for_task(self, task_id: int) -> list[dict[str, Any]]:
        """Retrieve all completed steps for a given task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks_steps WHERE task_id = ? AND status = 'COMPLETED' ORDER BY order_index ASC", (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_next_pending_step(self) -> dict[str, Any] | None:
        """Retrieve and claim the next pending step atomically."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "SELECT * FROM tasks_steps WHERE status = 'PENDING' ORDER BY order_index ASC LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    step_id = row['id']
                    conn.execute(
                        "UPDATE tasks_steps SET status = 'RUNNING', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (step_id,)
                    )
                    conn.commit()
                    row_dict = dict(row)
                    row_dict['status'] = 'RUNNING'
                    return row_dict
                else:
                    conn.rollback()
                    return None
            except Exception as e:
                conn.rollback()
                raise e

    def get_next_failed_step(self) -> dict[str, Any] | None:
        """Retrieve and claim the next failed step atomically."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "SELECT * FROM tasks_steps WHERE status = 'FAILED' ORDER BY order_index ASC LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    step_id = row['id']
                    # For failed steps, we might want to reset them to PENDING/RUNNING and increment retries?
                    # Or just leave them as FAILED and let the scheduler decide how to retry.
                    # The requirement says handles failures. Let's try setting it back to RUNNING for retry.
                    conn.execute(
                        "UPDATE tasks_steps SET status = 'RUNNING', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (step_id,)
                    )
                    conn.commit()
                    row_dict = dict(row)
                    row_dict['status'] = 'RUNNING'
                    return row_dict
                else:
                    conn.rollback()
                    return None
            except Exception as e:
                conn.rollback()
                raise e

    def complete_step(self, step_id: int, output_data: dict | None = None):
        """Mark a step as completed."""
        output_json = json.dumps(output_data) if output_data else None
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks_steps 
                SET status = 'COMPLETED', output_data = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """,
                (output_json, step_id),
            )
            conn.commit()

    def fail_step(self, step_id: int, error_msg: str):
        """Mark a step as failed."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks_steps 
                SET status = 'FAILED', error = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """,
                (error_msg, step_id),
            )
            conn.commit()

