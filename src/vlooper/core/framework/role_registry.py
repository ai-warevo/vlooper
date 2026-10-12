"""Module documentation."""

from typing import Any, Callable, Dict, Union, Protocol, runtime_checkable
from vlooper.infra.logger import get_logger
from vlooper.core.framework.context import TaskContext

logger = get_logger(__name__)

@runtime_checkable
class Agent(Protocol):
    """Protocol for objects that implement the agent interface."""
    def execute(self, ctx: TaskContext) -> Dict[str, Any]: ...

# Define the type for an executor. It can be a function or an object implementing Agent protocol.
RoleExecutor = Union[Callable[[TaskContext, Dict[str, Any]], Dict[str, Any]], Agent]

class RoleRegistry:
    """
    A registry that maps role identifiers to their corresponding 
    executor functions or agent objects.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, RoleExecutor] = {}

    def register(self, role_name: str, executor: RoleExecutor) -> None:
        """Registers a new role with an executor function or agent object."""
        if role_name in self._registry:
            logger.warning("Role '%s' is already registered and will be overwritten.", role_name)
        
        self._registry[role_name] = executor
        logger.debug("Registered role: %s", role_name)

    def get_executor(self, role_name: str) -> RoleExecutor | None:
        """Retrieves the executor for a given role name."""
        return self._registry.get(role_name)

    @property
    def registered_roles(self) -> list[str]:
        """Returns a list of all currently registered roles."""
        return list(self._registry.keys())

# Global instance for easy access/registration during startup
registry = RoleRegistry()
