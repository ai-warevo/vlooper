"""Module documentation."""

from typing import Any

from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


class TestPassedHandler:
    """Handles telemetry/logging when tests have passed successfully."""

    def handle(self, ctx_data: Any) -> None:
        """Logs telemetry information when tests have passed."""
        task_id = ctx_data.get("task_id")
        logger.info("[Telemetry] Task #%s: Tests passed successfully.", task_id)
