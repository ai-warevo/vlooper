import json
import os
import sys
import sqlite3

# Add current directory to sys.path so we can import vlooper
sys.path.append(os.getcwd())

from vlooper.config import config
from vlooper.persistence.database import Database
from vlooper.core.framework.role_registry import registry
from vlooper.core.daemon import VLooperDaemon
from vlooper.core.framework.context import TaskContext
from vlooper.infra.logger import get_logger

logger = get_logger("verification")

def run_verification():
    print("--- Starting Phase 2 Verification ---")
    
    # 1. Setup temporary database
    db_path = "/tmp/vlooper_verify.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path=db_path)

    # 2. Register Mock Roles
    def executor_1(ctx, brief):
        print("  [Executor 1] executing...")
        return {"step_1_output": "hello"}

    def executor_2(ctx, brief):
        print("  [Executor 2] executing with input:", brief)
        # Should receive data from step 1
        received = brief.get("step_1_output")
        return {"step_2_output": f"received_{received}"}

    def executor_3(ctx, brief):
        print("  [Executor 3] executing with input:", brief)
        return {"final": "success"}

    registry.register("mock_role_1", executor_1)
    registry.register("mock_role_2", executor_2)
    registry.register("mock_role_3", executor_3)

    # 3. Add a task and sequence of steps
    print("[Setup] Adding task and 3 steps...")
    db.add_task("ISSUE", "test/repo", "https://github.com/test/repo", 101, "main")
    # get_next_pending_task returns the row we just added
    task = db.get_next_pending_task()
    task_id = task["id"]

    db.add_step(task_id, "mock_role_1", 0, input_data={"init": True})
    db.add_step(task_id, "mock_role_2", 1) # Should receive output of step 1
    db.add_step(task_id, "mock_role_3", 2)

    # 4. Run Daemon logic manually to verify each step sequentially
    daemon = VLooperDaemon()
    # Override daemon's DB with our test DB
    daemon.db = db

    print("[Execution] Manually triggering step processing...")

    # Step 1 execution
    step1 = db.get_next_pending_step()
    assert step1 is not None, "Step 1 should be available"
    assert step1["role"] == "mock_role_1"
    daemon._process_step(step1)

    # Verify Step 1 completion and data injection into Step 2
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        s1 = conn.execute("SELECT status, output_data FROM tasks_steps WHERE id=?", (step1["id"],)).fetchone()
        assert s1 is not None
        assert s1["status"] == "COMPLETED"
        assert json.loads(s1["output_data"]) == {"step_1_output": "hello"}

        # Check if Step 2 input was updated
        s2 = conn.execute("SELECT input_data FROM tasks_steps WHERE role='mock_role_2'").fetchone()
        assert s2 is not None
        assert json.loads(s2["input_data"]) == {"step_1_output": "hello"}

    # Step 2 execution
    step2 = db.get_next_pending_step()
    assert step2 is not None, "Step 2 should be available"
    daemon._process_step(step2)

    # Verify Step 2 completion and data injection into Step 3
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        s2_row = conn.execute("SELECT status, output_data FROM tasks_steps WHERE id=?", (step2["id"],)).fetchone()
        assert s2_row is not None
        assert s2_row["status"] == "COMPLETED"
        assert json.loads(s2_row["output_data"]) == {"step_2_output": "received_hello"}

        # Check if Step 3 input was updated
        s3 = conn.execute("SELECT input_data FROM tasks_steps WHERE role='mock_role_3'").fetchone()
        assert s3 is not None
        assert json.loads(s3["input_data"]) == {"step_2_output": "received_hello"}

    # Step 3 execution
    step3 = db.get_next_pending_step()
    assert step3 is not None, "Step 3 should be available"
    daemon._process_step(step3)

    # Verify Step 3 completion
    with db._get_connection() as conn:
        conn.row_factory = sqlite3.Row
        s3_row = conn.execute("SELECT status, output_data FROM tasks_steps WHERE id=?", (step3["id"],)).fetchone()
        assert s3_row is not None
        assert s3_row["status"] == "COMPLETED"
        assert json.loads(s3_row["output_data"]) == {"final": "success"}

    print("--- VERIFICATION SUCCESSFUL ---")
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    try:
        run_verification()
    except Exception as e:
        print(f"--- VERIFICATION FAILED ---")
        print(e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
