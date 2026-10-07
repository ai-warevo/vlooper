"""Script to run all linters and checks in one command."""

import subprocess
import sys

from vlooper.logger import get_logger

logger = get_logger(__name__)


def run_command(command: list[str]) -> int:
    """Runs a system command and returns its return code."""
    logger.info(f"[{' '.join(command)}]▶️ Running...")
    try:
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            logger.info(f"[{' '.join(command)}]✅ Success!")
            return 0
        logger.error(f"❌ Error! Return code: {result.returncode}")
        return result.returncode
    except OSError as e:
        logger.error(f"❌ Failed to run command: {e}")
        return 1


def main() -> None:
    """Sequentially runs the entire code check stack."""
    commands = [
        ["black", "src", "tests"],
        ["ruff", "check", "--exit-zero", "src", "tests"],
        ["mypy", "src", "tests"],
        ["pylint", "src"],
        ["pylint", "--disable=C0114,C0115,C0116,W0621,W0212,R0801", "tests"],
    ]

    for cmd in commands:
        if run_command(cmd) != 0:
            logger.error("🚨 Some checks failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
