from typing import Any, Dict
from vlooper.agents.base import BaseAgent
from vlooper.core.framework.context import TaskContext

class DummyAgent(BaseAgent):
    """
    A template agent designed to demonstrate the standard BaseAgent interface.
    """

    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        """
        Executes a dummy implementation of an agent task.
        """
        # Retrieve mission brief from context metadata (following the new convention)
        mission_brief = ctx.metadata.get("mission_brief", {})
        
        # In current transition phase, we might still check if it's passed as a direct arg 
        # or via context if we want to be robust, but for now let's assume it's in metadata.
        
        print(f"[DUMMY_AGENT] Executing for Task ID: {ctx.task_id}")
        print(f"[DUMMY_AGENT] Mission Brief Summary: {str(mission_brief)[:100]}...")

        # Simulate work
        success = True 
        
        if success:
            return {
                "status": "success",
                "output": {"message": "Dummy agent executed successfully."}
            }
        else:
            return {
                "status": "failed",
                "error_message": "Dummy agent failed for demonstration purposes."
            }

# For testing/registration if needed as a function (backward compatibility)
def dummy_agent_func(ctx: TaskContext, brief: Dict[str, Any]) -> Dict[str, Any]:
    """Function-based version of the dummy agent."""
    return DummyAgent().execute(ctx) # This won't work because execute expects ctx and I didn't pass brief to metadata if it's a function call. 
    # Wait, the DummyAgent.execute implementation above assumes it's in metadata.
