# pylint: disable=redefined-outer-name,protected-access,unused-argument
"""Tests for the Scanner class."""

import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

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
    mock_issues = [
        {
            "number": 1,
            "title": "Test Issue",
            "body": "Describe it",
            "repository": {"nameWithOwner": "org/repo1"},
            "isPullRequest": False,
        }
    ]

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        print(f"DEBUG: Mock called with cmd={cmd}")
        if "gh" in cmd_str and "search" in cmd_str and "is:issue" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_issues), stderr=""
            )
        return CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Not a search command"
        )

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["repo_full_name"] == "org/repo1"
    assert pending[0]["branch_name"] == "issue-1"


def test_scan_prs(scanner, db, monkeypatch):
    """Test the PR scanning functionality."""
    mock_prs = [
        {
            "number": 42,
            "title": "Test PR",
            "body": "PR body",
            "repository": {"nameWithOwner": "org/repo-pr"},
            "isPullRequest": True,
        }
    ]
    mock_pr_details = {"headRefName": "feature-xyz"}

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        print(f"DEBUG: Mock called with cmd={cmd}")
        if "gh" in cmd_str and "search" in cmd_str and "is:pr" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_prs), stderr=""
            )
        if "gh" in cmd_str and "pr" in cmd_str and "view" in cmd_str:
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(mock_pr_details), stderr=""
            )
        return CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Unknown command"
        )

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["repo_full_name"] == "org/repo-pr"
    assert pending[0]["branch_name"] == "feature-xyz"
