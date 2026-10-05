"""Utility functions for vLooper."""

import subprocess


def build_gh_view_cmd(
    cmd_type: str, num: int, repo: str, fields: list[str]
) -> list[str]:
    """Строит базовую команду для gh issue view или gh pr view."""
    return [
        "gh",
        cmd_type,  # "issue" или "pr"
        "view",
        str(num),
        "--repo",
        repo,
        "--json",
        *fields,
    ]


def run_command(cmd, cwd=None, timeout=None):
    """Run a shell command with an optional timeout."""
    print(f"DEBUG: running command {cmd}")
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, check=False
        )
        if res.returncode != 0:
            error_msg = (
                f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\n"
                f"STDERR:\n{res.stderr}"
            )
            print(f"DEBUG: command failed with error: {error_msg}")
            return None, error_msg
        print(f"DEBUG: command success, stdout length: {len(res.stdout)}")
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
