"""Module documentation."""

from collections.abc import Callable

from vlooper.infra.logger import get_logger

from .context import TaskContext
from .event_bus import EventBus
from .types import Middleware, NextFn, StepFn

logger = get_logger(__name__)


class TaskPipeline:
    """
    The core orchestration engine for the vLooper automation daemon.
    It implements a pipeline architecture using middleware (onion layers)
    and sequential execution steps.
    """

    def __init__(self, event_bus: EventBus) -> None:
        """
        Initializes the TaskPipeline with a shared EventBus.

        Args:
            event_bus: The central event bus instance for reactivity and logging.
        """
        self._event_bus = event_bus
        self._middlewares: list[Middleware] = []
        self._steps: list[StepFn] = []
        self._step_descriptions: dict[int, str] = {}

    def use(self, middleware: Middleware) -> "TaskPipeline":
        """
        Registers a middleware to be applied around the execution stack.
        The first registered middleware will be the outermost layer of the onion.

        Args:
            middleware: A callable adhering to the Middleware protocol.

        Returns:
            Self for method chaining.
        """
        self._middlewares.append(middleware)
        return self

    def add_step(self, step: StepFn, description: str | None = None) -> "TaskPipeline":
        """
        Adds an automation step to be executed sequentially in the pipeline core.

        Args:
            step: A callable representing a unit of work that takes a TaskContext.
            description: An optional human-readable description for this step.

        Returns:
            Self for method chaining.
        """
        if description:
            self._step_descriptions[len(self._steps)] = description
        self._steps.append(step)
        return self

    def run(self, ctx: TaskContext) -> None:
        """
        Executes the pipeline. It wraps all registered steps in the onion layers
        provided by the registered middlewares.

        If `ctx.is_aborted` is set to True at any point (either via a step or a middleware),
        the execution will halt immediately.

        Args:
            ctx: The TaskContext containing the state for this pipeline run.
        """
        if ctx.is_aborted:
            return

        # Inject event bus into context metadata for access by steps/middlewares
        ctx.metadata["event_bus"] = self._event_bus

        # Define the core execution logic: iterate through all registered steps.
        def base_executor() -> None:
            for i, step in enumerate(self._steps):
                if ctx.is_aborted:
                    break

                step_name = getattr(step, "__name__", "anonymous_step")
                # Use a custom description if available, otherwise fallback to the function name.
                description = self._step_descriptions.get(i, step_name)
                logger.info("[step %d/%d] %s...", i + 1, len(self._steps), description)

                try:
                    step(ctx)
                except Exception:
                    logger.exception("[Step] Error in %s", step_name)
                    raise

        # The 'current_next' starts pointing to the base executor (the innermost part of the onion).
        current_next: NextFn = base_executor

        # Wrap current_next with middlewares, starting from the last one added
        # and moving towards the first one. This ensures that the FIRST middleware
        # registered becomes the OUTERMOST layer of the execution stack.
        for middleware in reversed(self._middlewares):
            # Capture the current state of the next function for this specific layer's closure.
            def make_next(m: Middleware, n: NextFn) -> Callable[[], None]:
                return lambda: m(ctx, n)

            current_next = make_next(middleware, current_next)

        # Begin execution from the outermost middleware.
        current_next()
