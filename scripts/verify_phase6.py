import sys
import os

# Mock dotenv before any other imports to avoid ModuleNotFoundError
try:
    import dotenv
except ImportError:
    import types
    m = types.ModuleType("dotenv")
    sys.modules["dotenv"] = m
    m.load_dotenv = lambda *args, **kwargs: None

# Add src to path so imports work correctly
sys.path.append(os.path.join(os.getcwd(), 'src'))

from vlooper.persistence.database import Database
from vlooper.services.scheduler_service import SchedulerService
from vlooper.config import config

def run_verification():
    print("--- Starting Phase 6 Verification ---")
    
    # Use the configured database
    db = Database()
    scheduler = SchedulerService(db)
    
    # RE-USE UNIQUE NAMES TO ENSURE FRESHNESS
    repo_name = f"test/repo_{os.getpid()}"

    # 1. Create a test task
    task_id = db.add_task("TEST_TASK", repo_name, "https://github.com/test/repo", 123, "test-branch")
    if not task_id:
        print("Error: Could not create task.")
        return

    print(f"Created Task ID: {task_id}")

    # 2. Add an initial step (e.g., issue_fetcher)
    step1_id = db.add_step(task_id, "issue_fetcher", 1, {"issue_number": 123})
    print(f"Added Step ID: {step1_id}, Role: issue_fetcher")

    # 3. Add the step we want to test (test_runner)
    step2_id = db.add_step(task_id, "test_runner", 2, {"some": "input"})
    print(f"Added Step ID: {step2_id}, Role: test_runner")

    # 4. Simulate completion with failure status in outcome
    failure_outcome = {
        "status": "failed",
        "output": {
            "exit_code": 1,
            "logs": "Critical test failures detected!"
        }
    }
    
    print(f"\nSimulating completion of Step #{step2_id} with failure outcome...")
    success = scheduler.react_to_step_outcome(step2_id, task_id, "test_runner", 2, failure_outcome)
    
    if success:
        print("SUCCESS: Reactive scheduler triggered injection.")
    else:
        print("FAILURE: Reactive scheduler did NOT trigger injection.")

    # 5. Verify the injection in DB
    new_steps = db.get_task_steps(task_id)
    print("\nFinal Step List in Database:")
    for s in new_steps:
        print(f"  - ID: {s['id']}, Role: {s['role']}, Order Index: {s['order_index']}, Status: {s['status']}")

    # Check if test_healer was added as the next step (Order index 3)
    has_healer = any(s['role'] == 'test_healer' and s['order_index'] == 3 for s in new_steps)
    if has_healer:
        print("\nVERIFICATION PASSED: test_healer correctly injected at order index 3.")
    else:
        print("\nVERIFICATION FAILED: test_healer not found where expected.")

if __name__ == "__main__":
    run_verification()
