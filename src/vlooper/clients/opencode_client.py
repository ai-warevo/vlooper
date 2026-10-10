"""Client for interacting with the Opencode CLI."""

from vlooper.config import config
from vlooper.infra.logger import get_logger
from vlooper.infra.utils import run_command

logger = get_logger(__name__)


class OpencodeClient:
    """Encapsulates execution of 'opencode run' commands."""

    def __init__(self, model: str | None = None):
        """
        Initialize the client with a specific model.
        Defaults to config.model_cfg.model if not provided.
        """
        self.model = model or config.model_cfg.model

    def run(
        self,
        prompt: str,
        cwd: str | None = None,
        timeout: int | None = None,
        truncate_lines: int | None = None,
    ) -> tuple[str | None, str | None]:
        """
        Executes an opencode run command with the given prompt.

        Args:
            prompt: The text input for the agent.
            cwd: The working directory to run the command in.
            timeout: Timeout in milliseconds.
            truncate_lines: Number of lines to keep on error.

        Returns:
            A tuple containing (stdout, err).
        """
        cmd = ["opencode", "run", "--model", self.model, prompt]
        logger.debug("Executing Opencode command: %s", " ".join(cmd))

        return run_command(
            cmd,
            cwd=cwd,
            timeout=timeout or config.timeouts.execution_timeout,
            truncate_lines=truncate_lines,
        )
