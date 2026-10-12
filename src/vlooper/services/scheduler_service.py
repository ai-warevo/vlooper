"""Module documentation."""

import json
from typing import Any, Dict, List, Optional
from vlooper.infra.logger import get_logger
from vlooper.persistence.database import Database


logger = get_logger(__name__)


class SchedulerService:
    """
    The 'Brain' of vLooper. 
    Responsible for initial planning (Issue -> Steps) and reactive re-planning (Failure -> Corrective Steps).
    """

    def __init__(self, db: Database):
        self.db = db

    def plan_initial_steps(self, task_id: int, issue_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyzes a new issue and generates an initial sequence of Steps in the database.
        
        In a full implementation, this would call an LLM to decide the sequence of roles.
        For now, we use a default standard sequence for most issues.
        """
        logger.info("Planning initial steps for Task #%s", task_id)
        
        # Standard initial pipeline: 
        # 1. issue_fetcher (to get more context if needed)
        # 2. git_isolator (to prepare workspace)
        # 3. text_runner (initial test run to see status) -- actually maybe not, let's start with fetcher and isolator.
        
        steps = [
            {"role": "issue_fetcher", "input_data": {"issue_number": issue_data.get("issue_number")}},
            {"role": "git_isolator", "input_data": {}},
        ]

        for idx, step in enumerate(steps):
            self.db.add_step(
                task_id=task_id,
                role=step["role"],
                order_index=idx + 1,
                input_data=step["input_data"]
            )
        
        logger.info("Successfully injected %d initial steps for Task #%s", len(steps), task_id)
        return steps

    def react_to_step_failure(self, step_id: int, task_id: int, role: str, error_msg: str) -> bool:
        """
        Reactive Re-planning: if a specific role fails, inject a corrective step.
        
        Returns True if a corrective step was injected, False otherwise.
        """
        logger.info("Evaluating reactive re-planning for failed step #%s (Role: %s)", step_id, role)

        # Determine the last successful step index to place the new one correctly
        all_steps = self.db.get_task_steps(task_id)
        if not all_steps:
            return False

        # Find the max order index currently in the system for this task
        max_idx = max(s["order_index"] for s in all_steps)
        
        # Logic for corrective steps:
        new_step: Optional[Dict[str, Any]] = None

        if role == "test_runner":
            logger.info("[SCHEDULER] Test failure detected. Injecting 'ai_fixer' step.")
            new_step = {
                "role": "ai_fixer",
                "input_data": {"error_context": error_msg}
            }
        elif role == "ai_fixer" and "syntax" in error_msg.lower():
             # If the AI fixer itself fails due to syntax, maybe we need a linter (if we had one)
             pass

        if new_step:
            # Inject it right after the current index or at the end? 
            # Usually we want it to be part of the flow. Let's put it as the next step.
            self.db.add_step(
                task_id=task_id,
                role=new_step["role"],
                order_index=max_idx + 1,
                input_data=new_step["input_data"]
            )
            logger.info("[SCHEDULER] Injected corrective step '%s' for Task #%s", new_step["role"], task_id)
            return True

        return False

