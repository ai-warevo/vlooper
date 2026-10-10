from vlooper.infra.logger import get_logger

from ..framework.context import TaskContext
from ..framework.types import NextFn

logger = get_logger(__name__)


class GlobalExceptionHandlerMiddleware:
    """
    A top-level middleware that wraps the entire pipeline execution in a
    try-except block to catch unforeseen bugs or exceptions from any step
    or subsequent middleware layer.
    """

    def __call__(self, ctx: TaskContext, next_fn: NextFn) -> None:
        try:
            next_fn()
        except Exception as e:
            logger.exception(
                "Uncaught exception detected at the top-level pipeline boundary"
            )
            ctx.is_aborted = True
            ctx.error = e
            if ctx.workspace_path and ctx.branch_name:
                from vlooper.services.git_service import quick_reset

                quick_reset(ctx.workspace_path)
