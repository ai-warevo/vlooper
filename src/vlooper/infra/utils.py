"""Utility functions for vLooper."""

import subprocess

from vlooper.infra.logger import get_logger


logger = get_logger(__name__)


def run_command(cmd, cwd=None, timeout=None, truncate_lines: int | None = None, input: str | None = None):
    """Run a shell command with an optional timeout and truncation."""
    logger.debug("running command %s", cmd)
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, check=False, input=input
        )
        if res.returncode != 0:
            stdout = res.stdout
            stderr = res.stderr

            if truncate_lines:
                st_lines = stdout.splitlines()
                if len(st_lines) > truncate_lines:
                    stdout = "\n".join(st_lines[-truncate_lines:])

                se_lines = stderr.splitlines()
                if len(se_lines) > truncate_lines:
                    stderr = "\n".join(se_lines[-truncate_lines:])

            error_msg = (
                f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )
            # We use ERROR level because a shell command failing is an actionable event.
            logger.error("Command failure: %s", error_msg)
            return None, error_msg
        logger.debug("command success, stdout length: %d", len(res.stdout))
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = e.stderr.decode() if e.stderr else ""

        if truncate_lines:
            st_lines = stdout.splitlines()
            if len(st_lines) > truncate_lines:
                stdout = "\n".join(st_lines[-truncate_lines:])
            se_lines = stderr.splitlines()
            if len(se_lines) > truncate_lines:
                stderr = "\n".join(se_lines[-truncate_lines:])

        error_msg = (
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        logger.error("Command timeout: %s", error_msg)
        return None, error_msg
    except Exception as e:  # noqa: W0718
        logger.error("Unexpected exception during command execution: %s", e)
        return None, str(e)
