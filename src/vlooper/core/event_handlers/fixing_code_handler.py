from typing import Any

from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


class FixingCodeHandler:
    """Handles telemetry/logging when the AI agent starts attempting a fix."""

    def handle(self, ctx_data: Any) -> None:
        task_id = ctx_data.get("task_id")
        logger.info(
            "[Telemetry] Task #%s: AI agent is attempting to apply a fix...", task_id
        )
