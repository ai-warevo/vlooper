from typing import Protocol, Callable
from .context import TaskContext

# Define a type for the next function in the middleware chain.
NextFn = Callable[[], None]

class Middleware(Protocol):
    """
    A protocol defining a middleware component that can intercept and 
    wrap execution steps in an onion-like architecture.
    """
    def __call__(self, ctx: TaskContext, next_fn: NextFn) -> None:
        ...

# A Step function represents a discrete unit of work within the pipeline.
StepFn = Callable[[TaskContext], None]
