"""Module documentation."""

from typing import Any, Dict
from vlooper.infra.logger import get_logger
from vlooper.core.framework.context import TaskContext

logger = get_logger(__name__)


class Synthesizer:
    """
    Responsible for preparing a "Mission Brief" (Action Instruction) 
    for a given role, based on the current task context and previous steps' output.
    """

    def prepare_mission_brief(self, ctx: TaskContext, role: str, input_data: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Synthesizes a dense instruction set for the worker.
        
        In this initial implementation, we simply merge the existing input_data 
        with some contextual information from the TaskContext.
        """
        logger.debug("Synthesizing mission brief for role: %s", role)

        # Start with the input data provided by the scheduler/previous step
        brief = input_data.copy() if input_data else {}

        # Add context as part of instructions (if needed by agents in later phases)
        # For now, we just ensure key information is present.
        brief["task_id"] = ctx.task_id
        brief["issue_number"] = ctx.issue_number
        brief["repo_full_name"] = ctx.repo_full_name or ""
        
        if ctx.issue_title:
            brief["issue_title"] = ctx.issue_title
        if ctx.issue_body:
            brief["issue_body"] = ctx.issue_body

        return brief
