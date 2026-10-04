"""Utility functions for vLooper."""

import subprocess


def run_command(cmd, cwd=None, timeout=None):
    """Run a shell command with an optional timeout."""
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, check=False
        )
        if res.returncode != 0:
            error_msg = (
                f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\n"
                f"STDERR:\n{res.stderr}"
            )
            return None, error_msg
        return res.stdout.strip(), None
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = e.stderr.decode() if e.stderr else ""
        error_msg = (
            f"Command timed out after {timeout}s: {' '.join(cmd)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        return None, error_msg
    except Exception as e:  # noqa: W0718
        return None, str(e)
