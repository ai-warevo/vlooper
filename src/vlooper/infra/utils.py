"""Utility functions for vLooper."""

import subprocess
import re

from vlooper.infra.logger import get_logger

logger = get_logger(__name__)


def filter_test_logs(logs: str) -> str:
    """
    Filters test logs to reduce noise from linters and style checkers,
    prioritizing actual failure information.
    """
    if not logs:
        return ""

    # Keywords that indicate high-signal failures or errors
    failure_patterns = [
        r"AssertionError",
        r"FAILED",
        r"Traceback \(most recent call last\):",
        r"Error:",
        r"Exception:",
        r"TypeError:",
        r"ValueError:",
        r"RuntimeError:",
    ]
    combined_failure_pattern = "|".join(failure_patterns)

    # Keywords that indicate linting/style noise to be de-prioritized or stripped
    noise_keywords = ["linter", "ruff", "pylint", "flake8", "style warning", "trailing whitespace", "unused import"]
    combined_noise_pattern = "|".join(noise_keywords)

    lines = logs.splitlines()
    filtered_lines = []
    has_failure = False

    # First pass: identify if there is a failure in the logs
    for line in lines:
        if re.search(combined_failure_pattern, line):
            has_failure = True
            break

    if not has_failure:
        # If there's no obvious failure, we likely have just linting noise or passing tests.
        # In this case, returning a short message helps the agent avoid getting lost in noise.
        return "No significant test failures detected in logs (tests might be passing or only showing style warnings)."

    # Second pass: Filter lines
    for line in lines:
        if re.search(combined_noise_pattern, line, re.IGNORECASE):
            # Even if it looks like noise, keep it if it's part of a traceback/failure
            if re.search(combined_failure_pattern, line):
                filtered_lines.append(line)
            else:
                continue
        else:
            filtered_lines.append(line)

    # If after filtering we still have too many lines, let's prioritize the end of the log 
    # where most tracebacks and error details reside.
    if len(filtered_lines) > 150:
        # Keep the top 20 lines (context/setup) and the bottom 130 lines (actual failure/traceback)
        return "\n".join(filtered_lines[:20] + ["... [truncated noise] ..."] + filtered_lines[-130:])

    return "\n".join(filtered_lines)


def run_command(
    cmd,
    cwd=None,
    timeout=None,
    truncate_lines: int | None = None,
    input_val: str | None = None,
):
    """Run a shell command with an optional timeout and truncation."""
    logger.debug("running command %s", cmd)
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            check=False,
            input=input_val,
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
