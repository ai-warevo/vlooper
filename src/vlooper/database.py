import sqlite3
from datetime import datetime
from vlooper.config import config

class Database:
    def __init__(self, db_path=config.db_path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
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
        # Check if task already exists to avoid duplicates
        if self.task_exists(repo_full_name, branch_name):
            return False
            
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (task_type, repo_full_name, branch_name, status)
                VALUES (?, ?, ?, 'PENDING')
            """, (task_type, repo_full_name, branch_name))
            conn.commit()
        return True

    def get_pending_tasks(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE status = 'PENDING'")
            return cursor.fetchall()

    def claim_task(self, task_id):
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE tasks 
                SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP 
                WHERE id = ? AND (status = 'PENDING' OR (status = 'FAILED' AND retries < ?))
            """, (task_id, config.max_retries))
            conn.commit()
            return cursor.rowcount > 0

    def complete_task(self, task_id):
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (task_id,))
            conn.commit()

    def fail_task(self, task_id, error_msg):
        with self._get_connection() as conn:
            # Check retries
            cursor = conn.execute("SELECT retries FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row and row[0] < config.max_retries:
                conn.execute("""
                    UPDATE tasks 
                    SET status = 'PENDING', retries = retries + 1, last_error = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (error_msg, task_id))
            else:
                conn.execute("""
                    UPDATE tasks 
                    SET status = 'FAILED', last_error = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (error_msg, task_id))
            conn.commit()

    def get_active_claimed_task(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE status = 'CLAIMED'")
            return cursor.fetchone()

    def task_exists(self, repo_full_name, branch_name):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM tasks WHERE repo_full_name = ? AND branch_name = ?", 
                (repo_full_name, branch_name)
            )
            return cursor.fetchone() is not None
