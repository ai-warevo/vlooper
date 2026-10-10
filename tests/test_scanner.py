import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from vlooper.config import config
from vlooper.persistence.database import Database
from vlooper.core.scanner import Scanner


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def scanner(db):
    """Create a scanner instance."""
    return Scanner(db)


def test_scan_issues(scanner, db, monkeypatch):
    """Test the issue scanning functionality."""
    monkeypatch.setattr(config.git, "authorized_users", ["bot_user"])
    mock_issues = [
        {
            "number": 1,
            "title": "Test Issue",
            "body": "Describe it",
            "repository": {"nameWithOwner": "org/repo1"},
            "isPullRequest": False,
            "author": {"login": "bot_user"},
        }
    ]

    def mock_run(cmd, *_args, **_kwargs):
        cmd_str = " ".join([str(x) for x in cmd]) if isinstance(cmd, list) else str(cmd)
        if "is:issue" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_issues), stderr=""
            )
        if "is:pr" in cmd_str:
            return CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")
        return CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Unknown command"
        )

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["repo_full_name"] == "org/repo1"
    assert pending[0]["branch_name"] == "issue-1"


def test_scan_prs(scanner, db, monkeypatch):
    """Test the PR scanning functionality."""
    monkeypatch.setattr(config.git, "authorized_users", ["bot_user"])
    mock_prs = [
        {
            "number": 42,
            "title": "Test PR",
            "body": "PR body",
            "repository": {"nameWithOwner": "org/repo-pr"},
            "isPullRequest": True,
            "author": {"login": "bot_user"},
        }
    ]
    mock_pr_details = {"headRefName": "feature-xyz"}

    def mock_run(cmd, *_args, **_kwargs):
        cmd_str = " ".join([str(x) for x in cmd]) if isinstance(cmd, list) else str(cmd)
        if "is:pr" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_prs), stderr=""
            )
        if "view" in cmd_str and "pr" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_pr_details), stderr=""
            )
        if "is:issue" in cmd_str:
            return CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")
        return CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Unknown command"
        )

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["repo_full_name"] == "org/repo-pr"
    assert pending[0]["branch_name"] == "feature-xyz"
