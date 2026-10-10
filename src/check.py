"""Module documentation."""

import os
import subprocess
import sys


def main() -> None:
    """Runs linters and formatters (black, ruff, mypy, pylint)."""
    print("🚀 Running project checks...")

    commands = [
        ("Black", ["black", "--check", "src", "tests"]),
        ("Ruff", ["ruff", "check", "--exit-zero", "src", "tests"]),
        ("Mypy", ["mypy", "tests", "src/vlooper", "src/analyze_unused.py"]),
        ("Pylint (src)", ["pylint", "src"]),
        (
            "Pylint (tests)",
            ["pylint", "--disable=C0114,C0115,C0116,W0621,W0212,R0801", "tests"],
        ),
    ]

    failed = False
    for name, cmd in commands:
        print(f"\n--- Running {name} ---")
        env = None
        if name == "Mypy":
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
        res = subprocess.run(cmd, check=False, env=env)
        if res.returncode != 0:
            failed = True

    if not failed:
        print("\n✅ All checks passed!")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
