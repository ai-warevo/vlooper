from typing import Any
from vlooper.infra.logger import get_logger

logger = get_logger(__name__)

class TaskStatusHandler:
    """Handles updating task status in the database when a task completes."""
    def __init__(self, db: Any) -> None:
        self.db = db

    def handle(self, ctx: Any) -> None:
        """Updates the database with final results from the pipeline execution."""
        try:
            if ctx.is_aborted or (ctx.exit_code is not None and ctx.exit_code != 0):
                error_msg = str(ctx.error) if ctx.error else f"Pipeline failed with exit code {ctx.exit_code}"
                logger.info("📝 Finalizing task #%s as FAILED: %s", ctx.task_id, error_msg)
                self.db.fail_task(ctx.task_id, error_msg)
            else:
                logger.info("📝 Finalizing task #%s as COMPLETED.", ctx.task_id)
                self.db.complete_task(ctx.task_id)
        except Exception as e:
            logger.error("❌ Failed to update database for task #%s: %s", ctx.task_id, e)
