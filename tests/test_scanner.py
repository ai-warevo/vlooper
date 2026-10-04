import json
import subprocess
import pytest
from unittest.mock import MagicMock, patch
from vlooper.scanner import Scanner
from vlooper.database import Database

@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))

@pytest.fixture
def scanner(db):
    return Scanner(db)

def test_scan_issues(scanner, db, monkeypatch):
    # Mock the subprocess call inside run_command/Scanner._scan_issues
    mock_issues = [
        {
            "number": 1,
            "title": "Test Issue",
            "body": "Describe it",
            "repository": {"nameWithOwner": "org/repo1"}
        }
    ]
    
    def mock_run(cmd, capture_output=True, text=True):
        # Check if the call is for gh search issues
        if "gh" in cmd and "search" in cmd and "type:issue" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(mock_issues), stderr="")
        return MagicMock(returncode=1, stdout="", stderr="Not a search command")

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    # Verify task was added to DB
    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]['repo_full_name'] == "org/repo1"
    assert pending[0]['branch_name'] == "issue-1"

def test_scan_prs(scanner, db, monkeypatch):
    # Mock the two calls: 1. search prs, 2. get branch details via gh pr view
    mock_prs = [
        {
            "number": 42,
            "title": "Test PR",
            "body": "PR body",
            "repository": {"nameWithOwner": "org/repo-pr"}
        }
    ]
    mock_pr_details = {
        "headRefName": "feature-xyz"
    }

    def mock_run(cmd, capture_output=True, text=True):
        if "gh" in cmd and "search" in cmd and "type:pr" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(mock_prs), stderr="")
        if "gh" in cmd and "pr" in cmd and "view" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(mock_pr_details), stderr="")
        return MagicMock(returncode=1, stdout="", stderr="Unknown command")

    with patch("subprocess.run", side_effect=mock_run):
        scanner.scan()

    # Verify task was added to DB
    pending = db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]['repo_full_name'] == "org/repo-pr"
    assert pending[0]['branch_name'] == "feature-xyz"
