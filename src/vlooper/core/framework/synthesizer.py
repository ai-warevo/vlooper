"""Module documentation."""

import json
from typing import Any, Dict, List, Optional
from vlooper.infra.logger import get_logger
from vlooper.core.framework.context import TaskContext


logger = get_logger(__name__)


class Synthesizer:
    """
    Responsible for preparing a "Mission Brief" (Action Instruction) 
    for a given role, based on the current task context and previous steps' output.
    """

    def prepare_mission_brief(
        self, 
        ctx: TaskContext, 
        role: str, 
        input_data: Dict[str, Any], 
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a dense instruction set for the worker.
        
        This implementation compresses [Global Goal + Step History + Current Step Requirements]
        into a single, high-signal 'mission_brief' string within the return dictionary.
        """
        logger.debug("Synthesizing mission brief for role: %s", role)

        # 1. Build the "Contextual Core" (The history of what happened so far)
        history_summary = ""
        if history:
            history_lines = []
            for step in history:
                status = step.get("status")
                prev_role = step.get("role")
                output = step.get("output_data")
                
                if status == "COMPLETED" and output:
                    # We compress the output if it's too large, but for now just summarize
                    output_str = str(output)
                    if len(output_str) > 500:
                        output_str = output_str[:500] + "... [truncated]"
                    history_lines.append(f"- {prev_role} completed: {output_str}")
                elif status == "FAILED":
                    error = step.get("error")
                    history_lines.append(f"- {prev_role} FAILED with error: {error}")
            
            if history_lines:
                history_summary = "\n".join(history_lines)

        # 2. Build the Instruction Set
        instruction = (
            f"ROLE: {role}\n"
            f"GOAL: Address issue #{ctx.issue_number}: {ctx.issue_title or ctx.metadata.get('original_task', {}).get('issue_title', 'Unknown Issue')}\n"
            f"REPO: {ctx.repo_full_name or ctx.repo_url}\n\n"
        )

        if history_summary:
            instruction += f"PREVIOUS STEPS HISTORY:\n{history_summary}\n\n"

        instruction += "CURRENT MISSION REQUIREMENTS:\n"
        if input_data:
            # Pretty print the input data for clarity in instructions
            instruction += f"{json.dumps(input_data, indent=2)}\n"
        else:
            instruction += "No specific input data provided for this step.\n"

        instruction += "\nACTION: Execute your role's responsibility based on the information above. "
        instruction += "Return ONLY a JSON object containing any relevant results or findings."

        # 3. Final assembly
        return {
            "task_id": ctx.task_id,
            "issue_number": ctx.issue_number,
            "repo_full_name": ctx.repo_full_name or "",
            "mission_brief": instruction,
            "raw_input": input_data # Keep raw input for the worker to use directly if needed
        }
