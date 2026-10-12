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
        """
        logger.info("Planning initial steps for Task #%s", task_id)
        
        steps = [
            {"role": "issue_fetcher", "input_data": {"issue_number": issue_data.get("issue_number")}},
            {"role": "git_isolator", "input_data": {}},
            {"role": "linter_bot", "input_data": {}},
            {"role": "test_runner", "input_data": {}},
            {"role": "coverage_booster", "input_data": {}},
            {"role": "github_pr_creator", "input_data": {}},
            {"role": "pr_reviewer", "input_data": {}},
        ]
        
        for idx, step in enumerate(steps):
            # Use large gaps (1000) between initial steps to allow room for 
            # reactive corrective steps without requiring database shifts.
            self.db.add_step(
                task_id=task_id,
                role=step["role"],
                order_index=(idx + 1) * 1000,
                input_data=step["input_data"]
            )
        
        logger.info("Successfully injected %d initial steps for Task #%s", len(steps), task_id)
        return steps

    def react_to_step_outcome(self, step_id: int, task_id: int, role: str, order_index: int, outcome: Dict[str, Any]) -> bool:
        """
        Reactive Re-planning: if a specific role fails or provides negative feedback, inject a corrective step.
        
        Returns True if a corrective step was injected, False otherwise.
        """
        logger.info("Evaluating reactive re-planning for step #%s (Role: %s) with outcome status: %s", 
                    step_id, role, outcome.get("status"))

        # Retrieve all steps to check loop prevention and find insertion point
        all_steps = self.db.get_task_steps(task_id)
        if not all_steps:
            return False

        # Loop prevention: Limit the number of corrective/total steps in a task lifecycle
        # A reasonable limit for this phase is 15 steps to prevent infinite loops.
        if len(all_steps) > 15:
            logger.warning("[SCHEDULER] Task #%s has exceeded step limit (%d). Skipping reactive injection.", task_id, len(all_steps))
            return False

        new_step: Optional[Dict[str, Any]] = None
        status = outcome.get("status")
        output = outcome.get("output", {})
        
        # Pattern Mapping logic
        if status in ["failed", "error"]:
            if role == "test_runner":
                logger.info("[SCHEDULER] Test failure detected. Injecting 'test_healer' step.")
                new_step = {
                    "role": "test_healer",
                    "input_data": {"context": str(output)}
                }
            elif role == "linter_bot":
                logger.info("[SCHEDULER] Linter errors detected. Injecting 'ai_fixer' step.")
                new_step = {
                    "role": "ai_fixer",
                    "input_data": {"context": str(output)}
                }
        elif status == "success":
            if role == "pr_reviewer":
                # Check if the PR review output contains critical feedback indicators
                is_critical = (
                    output.get("critical_feedback") is True or 
                    "REJECTED" in str(output).upper() or
                    "CHANGES_REQUESTED" in str(output).upper()
                )
                if is_critical:
                    logger.info("[SCHEDULER] PR Reviewer reported critical feedback. Injecting 'review_fixer' step.")
                    new_step = {
                        "role": "review_fixer",
                        "input_data": {"context": str(output)}
                    }

        if new_step:
            self.db.add_step(
                task_id=task_id,
                role=new_step["role"],
                order_index=order_index + 1,
                input_data=new_step["input_data"]
            )
            logger.info("[SCHEDULER] Injected corrective step '%s' at order index %d for Task #%s", 
                        new_step["role"], order_index + 1, task_id)
            return True


        return False

    def react_to_step_failure(self, step_id: int, task_id: int, role: str, error_msg: str) -> bool:
        """Legacy shim for backward compatibility (mapping to react_to_step_outcome)."""
        return self.react_to_step_outcome(step_id, task_id, role, 0, {"status": "error", "error_message": error_msg})

