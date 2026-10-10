"""Module docstring."""

from vlooper.config import config
from vlooper.infra.logger import get_logger

from ..framework.context import TaskContext
from ..framework.types import NextFn

logger = get_logger(__name__)


class RetryLimitMiddleware:
    """
    A middleware that wraps the execution pipeline in a retry loop.
    It allows for a fixed number of attempts to complete the automation cycle.
    If the maximum number of attempts is reached and the task has not
    succeeded (exit_code != 0), it aborts the entire pipeline.
    """

    def __init__(self, max_pipeline_attempts: int | None = None) -> None:
        self._max_pipeline_attempts = (
            max_pipeline_attempts
            if max_pipeline_attempts is not None
            else config.timeouts.max_pipeline_attempts
        )

    def __call__(self, ctx: TaskContext, next_fn: NextFn) -> None:
        # Retrieve the current attempt count from metadata.
        attempt_count = ctx.metadata.get("attempt_count", 0)

        while attempt_count < self._max_pipeline_attempts:
            attempt_count += 1
            ctx.metadata["attempt_count"] = attempt_count

            logger.info(
                "Attempt %d of %d starting...",
                attempt_count,
                self._max_pipeline_attempts,
            )

            # Execute the next layer in the onion (could be more middleware or steps).
            next_fn()

            # Check if we reached a successful state.
            # We define success as tests passing (exit_code == 0).
            if ctx.exit_code == 0:
                logger.info("Automation cycle succeeded on attempt %d.", attempt_count)
                return

            # If the loop continues, we might be fixing things in the next step.
            # We only abort if this was our LAST allowed attempt and it still failed.
            if attempt_count >= self._max_pipeline_attempts:
                logger.error(
                    "Maximum attempts (%d) reached without successful test pass. Aborting.",
                    self._max_pipeline_attempts,
                )
                ctx.is_aborted = True
                return

            logger.warning(
                "Attempt %d failed. Proceeding to next step in pipeline (e.g., Fix).",
                attempt_count,
            )
