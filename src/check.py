"""Script to run all linters and checks in one command."""

import subprocess
import sys


def run_command(command: list[str]) -> int:
    """Runs a system command and returns its return code."""
    print(f"▶️ Running: {' '.join(command)}...")
    try:
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            print("✅ Success!")
            return 0
        print(f"❌ Error! Return code: {result.returncode}")
        return result.returncode
    except OSError as e:
        print(f"❌ Failed to run command: {e}")
        return 1


def main() -> None:
    """Sequentially runs the entire code check stack."""
    commands = [
        ["black", "src", "tests"],
        ["ruff", "check", "src", "tests"],
        ["mypy", "src", "tests"],
        ["pylint", "src"],
        ["pylint", "--disable=C0114,C0115,C0116,W0621,W0212,R0801", "tests"],
    ]

    for cmd in commands:
        if run_command(cmd) != 0:
            print("🚨 Some checks failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
