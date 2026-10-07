from unittest.mock import patch
import os

import pytest

from vlooper.config import config
from vlooper.database import Database
from vlooper.worker import Worker


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def worker(db):
    """Create a worker instance."""
    return Worker(db)


def test_delete_local_branch_with_detach_fallback(worker, monkeypatch, tmp_path):
    """Verify that _delete_local_branch falls back to --detach if main/master checkout fails."""
    monkeypatch.setattr(config, "workspace_base_dir", str(tmp_path / "workspace"))

    branch_name = "test-branch"
    repo_dir = str(tmp_path / "repo")
    os.makedirs(repo_dir, exist_ok=True)

    called_commands = []

    def side_effect_run(cmd, _cwd=None, _timeout=None, **_kwargs):
        cmd_str = " ".join(cmd)
        called_commands.append(cmd_str)

        # Mock successful setups
        if "git reset" in cmd_str or "git clean" in cmd_str:
            return "", None

        if any(
            x in cmd_str for x in ["git checkout -f main", "git checkout -f master"]
        ):
            return None, "branch not found"

        if "git checkout --detach" in cmd_str:
            return "", None

        if f"git branch -D {branch_name}" in cmd_str:
            return "", None

        if any(x in cmd_str for x in ["gh repo clone", "git checkout -B"]):
            return "", None

        return "", None

    with (
        patch("vlooper.worker.run_command", side_effect=side_effect_run),
        patch.object(Worker, "_get_context", return_value="test context"),
    ):
        # We call the method directly to test it
        worker._delete_local_branch(repo_dir, branch_name)

    # Check if git checkout --detach was called as a fallback
    assert any(
        "git checkout --detach" in cmd for cmd in called_commands
    ), f"Expected 'git checkout --detach' to be called, but got {called_commands}"

    # Check if git branch -D was still called
    delete_cmd = f"git branch -D {branch_name}"
    assert any(
        delete_cmd in cmd for cmd in called_commands
    ), f"Expected {delete_cmd} to be called, but got {called_commands}"
