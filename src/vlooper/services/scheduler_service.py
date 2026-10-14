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
        Uses LLM to classify if the issue is a 'feature' or a 'bug'.
        """
        logger.info("Planning initial steps for Task #%s", task_id)

        issue_title = issue_data.get("issue_title") or "No title"
        issue_body = issue_data.get("issue_body") or "No body"

        # Determine initial plan based on LLM classification
        is_feature = False  # Default to bug per robustness requirement
        try:
            logger.info("[SCHEDULER] Attempting task type classification via LLM...")
            client = OpencodeClient()
            classification_prompt = (
                "Analyze the following GitHub issue and classify it as either 'feature' or 'bug'. "
                "A 'feature' is a new piece of functionality or requirement. "
                "A 'bug' is a fix for existing broken behavior, an error, or unintended side effect.\n\n"
                f"Title: {issue_title}\n"
                f"Body: {issue_body}\n\n"
                "Return ONLY the single word 'feature' or 'bug'."
            )
            result, err = client.run(classification_prompt)

            if err:
                logger.warning("[SCHEDULER] Classification failed due to error: %s. Defaulting to 'bug'.", err)
            elif result:
                classification = result.strip().lower()
                # Robust check for the presence of target words
                if "feature" in classification and "bug" not in classification:
                    is_feature = True
                    logger.info("[SCHEDULER] Classification successful: Task is a FEATURE.")
                elif "bug" in classification:
                    is_feature = False
                    logger.info("[SCHEDULER] Classification successful: Task is a BUG.")
                else:
                    logger.warning("[SCHEDULER] Unexpected classification output: '%s'. Defaulting to 'bug'.", result)
            else:
                logger.warning("[SCHEDULER] Classification returned empty result. Defaulting to 'bug'.")

        except Exception as e:
            logger.error("[SCHEDULER] Exception during task type classification: %s. Defaulting to 'bug'.", e, exc_info=True)
            is_feature = False

        logger.info("Task #%s classified as %s", task_id, "feature" if is_feature else "bug")

        if is_feature:
            steps = [
                {"role": "gh_issue_fetcher", "input_data": {"issue_number": issue_data.get("issue_number")}},
                {"role": "feature_implementer", "input_data": {}},
                {"role": "linter_bot", "input_data": {}},
                {"role": "test_runner", "input_data": {}},
                {"role": "test_coverage_booster", "input_data": {}},
                {"role": "git_pusher", "input_data": {}},
                {"role": "gh_pr_manager", "input_data": {}},
                {"role": "gh_pr_reviewer", "input_data": {}},
            ]
        else:
            steps = [
                {"role": "gh_issue_fetcher", "input_data": {"issue_number": issue_data.get("issue_number")}},
                {"role": "git_isolator", "input_data": {}},
                {"role": "linter_bot", "input_data": {}},
                {"role": "test_runner", "input_data": {}},
                {"role": "test_coverage_booster", "input_data": {}},
                {"role": "git_pusher", "input_data": {}},
                {"role": "gh_pr_manager", "input_data": {}},
                {"role": "gh_pr_reviewer", "input_data": {}},
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
                logs_text = str(output.get("logs", "")).lower()
                # Heuristic to decide if it's a bug or an environment issue
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
                # Determine if feedback is critical (requires changes) using LLM for higher precision
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
                            # Fallback to simple keyword matching if LLM fails
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
                # After a successful fix, re-trigger the validation pipeline to ensure quality.
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
