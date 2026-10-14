import sys
import os
from unittest.mock import MagicMock

# Mock dotenv before anything else imports it
sys.modules["dotenv"] = MagicMock()

# Add src to PYTHONPATH so we can import vlooper
sys.path.append(os.path.join(os.getcwd(), 'src'))

import unittest
import sqlite3
import json

from vlooper.persistence.database import Database

class TestPersistenceV1(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_vlooper.db"
        # Ensure any old test DB is gone
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_task_with_meta(self):
        """Test adding a task with meta information."""
        meta = json.dumps({"issue": "fix linting error in main.py"})
        success = self.db.add_task(
            "ISSUE", 
            "test/repo", 
            "https://github.com/test/repo", 
            123, 
            "fix-lint", 
            meta=meta
        )
        self.assertTrue(success)

        tasks = self.db.get_all_tasks()
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task['meta'], meta)

    def test_step_lifecycle(self):
        """Test the full lifecycle of a step: create -> claim -> complete."""
        # 1. Create Task
        self.db.add_task("ISSUE", "test/repo", "url", 1, "branch")
        tasks = self.db.get_all_tasks()
        task_id = tasks[0]['id']

        # 2. Add Steps
        self.db.add_step(task_id, "linter_bot", 1, {"files": ["main.py"]})
        self.db.add_step(task_id, "test_healer", 2)
        self.db.add_step(task_id, "git_pusher", 3)

        # 3. Claim Step 1
        step1 = self.db.get_next_pending_step()
        self.assertIsNotNone(step1)
        self.assertEqual(step1['role'], "linter_bot")
        self.assertEqual(step1['order_index'], 1)
        self.assertEqual(step1['status'], "RUNNING")

        # 4. Complete Step 1
        output = {"status": "success", "fixed_files": ["main.py"]}
        self.db.complete_step(step1['id'], output)

        # Verify Step 1 is COMPLETED in DB
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT * FROM tasks_steps WHERE id = ?", (step1['id'],)).fetchone()
            self.assertEqual(res['status'], "COMPLETED")
            self.assertEqual(json.loads(res['output_data']), output)

        # 5. Claim and Fail Step 2
        step2 = self.db.get_next_pending_step()
        self.assertIsNotNone(step2)
        self.assertEqual(step2['role'], "test_healer")
        self.assertEqual(step2['order_index'], 2)
        self.assertEqual(step2['status'], "RUNNING")

        error_msg = "Tests failed"
        self.db.fail_step(step2['id'], error_msg)

        # Verify Step 2 is FAILED in DB
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT * FROM tasks_steps WHERE id = ?", (step2['id'],)).fetchone()
            self.assertEqual(res['status'], "FAILED")
            self.assertEqual(res['error'], error_msg)

        # 6. Claim Step 3
        step3 = self.db.get_next_pending_step()
        self.assertIsNotNone(step3)
        self.assertEqual(step3['role'], "git_pusher")
        self.assertEqual(step3['order_index'], 3)
        self.assertEqual(step3['status'], "RUNNING")

if __name__ == '__main__':
    unittest.main()
