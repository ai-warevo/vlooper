from abc import ABC, abstractmethod
from typing import Any, Dict
from vlooper.core.framework.context import TaskContext

class BaseAgent(ABC):
    """
    Abstract base class for all Active Agents in vLooper.
    All specialized agents must implement the `execute` method.
    """

    @abstractmethod
    def execute(self, ctx: TaskContext) -> Dict[str, Any]:
        """
        Execute the agent's logic using the provided TaskContext.
        
        Args:
            ctx: The current TaskContext containing all necessary state and metadata.
                The 'mission_brief' should be retrieved from `ctx.metadata`.

        Returns:
            A dictionary containing at least 'status' and optionally 'output' or 'error_message'.
            Example: {"status": "success", "output": {"applied": True}}
        """
        pass
