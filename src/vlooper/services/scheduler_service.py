"""Module documentation."""

import json
from typing import Any, Dict, List, Optional
from vlooper.clients.opencode_client import OpencodeClient
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
        Always starts with fetching the issue and then classifying it via the dedicated task_classifier_agent.
        """
        logger.info("Planning initial steps for Task #%s", task_id)

        # We only inject the first two steps: fetcher and classifier.
        # The rest of the plan depends on the classification outcome handled in react_to_step_outcome.
        steps = [
            {"role": "gh_issue_fetcher", "input_data": {"issue_number": issue_data.get("issue_number")}},
            {"role": "task_classifier_agent", "input_data": {}}, 
        ]
        
        for idx, step in enumerate(steps):
            # Use large gaps (1000) to allow room for subsequent reactive steps.
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
        if len(all_steps) > 15:
            logger.warning("[SCHEDULER] Task #%s has exceeded step limit (%d). Skipping reactive injection.", task_id, len(all_steps))
            return False

        new_step: Optional[Dict[str, Any]] = None
        status = outcome.get("status")
        output = outcome.get("output", {})

        # 1. Handle Task Classification Decision (The "Branching" logic)
        if role == "task_classifier_agent" and status == "success":
            task_type = output.get("task_type", "bug") # Default to bug if not found
            logger.info("[SCHEDULER] Classifier decided: %s. Generating plan for Task #%s.", task_type, task_id)

            if task_type == "feature":
                plan_roles = [
                    "feature_implementer", 
                    "linter_bot", 
                    "test_runner", 
                    "test_coverage_booster", 
                    "git_pusher", 
                    "gh_pr_manager", 
                    "gh_pr_reviewer"
                ]
            else:
                plan_roles = [
                    "git_isolator", 
                    "linter_bot", 
                    "test_runner", 
                    "test_coverage_booster", 
                    "git_pusher", 
                    "gh_pr_manager", 
                    "gh_pr_reviewer"
                ]

            for i, v_role in enumerate(plan_roles):
                self.db.add_step(
                    task_id=task_id,
                    role=v_role,
                    order_index=order_index + 10 + (i * 1000), # Offset after classifier
                    input_data={}
                )
            logger.info("[SCHEDULER] Injected %d subsequent steps for task type '%s'", len(plan_roles), task_type)
            return True

        # 2. Pattern Mapping logic for other roles...
        if status in ["failed", "error"]:
            if role == "test_runner":
                logs_text = str(output.get("logs", "")).lower()
                env_indicators = ["module not found", "command not found", "import error", "permission denied", "dependency", "missing"]
                is_env_issue = any(indicator in logs_text for indicator in env_indicators)

                if is_env_issue:
                    logger.info("[SCHEDULER] Test environment issue detected. Injecting 'test_healer' step.")
                    new_step = {
                        "role": "test_healer",
                        "input_data": {"context": str(output)}
                    }
                else:
                    logger.info("[SCHEDULER] Test logic failure detected. Injecting 'bug_fixer' step.")
                    new_step = {
                        "role": "bug_fixer",
                        "input_data": {"context": str(output)}
                    }

            elif role == "linter_bot":
                logger.info("[SCHEDULER] Linter errors detected. Injecting 'ai_fixer' step.")
                new_step = {
                    "role": "ai_fixer",
                    "input_data": {"context": str(output)}
                }

        elif status == "success":
            if role == "gh_pr_reviewer":
                # Smart criticality detection logic (maintained)
                is_critical = output.get("critical_feedback") is True

                if not is_critical:
                    try:
                        logger.info("[SCHEDULER] Attempting smart criticality analysis via LLM...")
                        client = OpencodeClient()
                        review_text = str(output.get("logs", ""))
                        criticality_prompt = (
                            "Analyze the following GitHub PR review feedback and determine if it requires changes "
                            "from the developer or if the PR has been rejected.\n\n"
                            "If the reviewer is asking for fixes, improvements, mandatory changes, or has rejected "
                            "the PR, respond with 'true'. \n"
                            "If the review is purely celebratory, informational, or contains only non-blocking "
                            "minor suggestions (e.g., 'LGTM', 'nice work', or minor nits that don't require changes), "
                            "respond with 'false'.\n\n"
                            f"Review Feedback: {review_text}\n\n"
                            "Return ONLY the single word 'true' or 'false'."
                        )
                        result, err = client.run(criticality_prompt)

                        if err:
                            logger.warning("[SCHEDULER] Smart criticality analysis failed: %s. Falling back to keyword matching.", err)
                            logs_text_upper = review_text.upper()
                            is_critical = (
                                "REJECTED" in logs_text_upper or
                                "REQUESTING CHANGES" in logs_text_upper or
                                "REQUEST CHANGES" in logs_text_upper or
                                "CHANGES REQUESTED" in logs_text_upper
                            )
                        elif result:
                            classification = result.strip().lower()
                            is_critical = ("true" in classification) and ("false" not in classification)
                            logger.info("[SCHEDULER] Smart criticality analysis result: %s", is_critical)
                        else:
                            logger.warning("[SCHEDULER] Smart criticality analysis returned empty result. Defaulting to False.")
                    except Exception as e:
                        logger.error("[SCHEDULER] Exception during smart criticality analysis: %s. Defaulting to False.", e)

                if is_critical:
                    logger.info("[SCHEDULER] PR Reviewer reported critical feedback. Injecting 'gh_pr_review_fixer' step.")
                    new_step = {
                        "role": "gh_pr_review_fixer",
                        "input_data": {"context": str(output)}
                    }
            elif role == "gh_pr_review_fixer":
                logger.info("[SCHEDULER] Review fixer completed successfully. Re-triggering validation pipeline.")
                validation_roles = [
                    "linter_bot", 
                    "test_runner", 
                    "test_coverage_booster", 
                    "git_pusher",
                    "gh_pr_manager",
                    "gh_pr_reviewer"
                ]
                for i, v_role in enumerate(validation_roles):
                    self.db.add_step(
                        task_id=task_id,
                        role=v_role,
                        order_index=order_index + 10 + (i * 1000),
                        input_data={}
                    )
                return True

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
