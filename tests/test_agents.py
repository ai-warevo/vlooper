import pytest
from unittest.mock import patch, MagicMock
from vlooper.core.framework.context import TaskContext
from vlooper.agents.git_isolator import git_isolator_agent
from vlooper.agents.agent_test_runner import test_runner_agent
from vlooper.agents.ai_fixer import ai_fixer_agent
from vlooper.services.github_service import clone_repository_workflow, post_github_comment, get_issue_number
from vlooper.clients.opencode_client import OpencodeClient
from vlooper.clients.git_client import has_uncommitted_changes

@pytest.fixture
def mock_ctx():
    return TaskContext(
        task_id="1",
        task_type="ISSUE",
        issue_number=123,
        repo_url="https://github.com/org/repo.git",
        workspace_path="/tmp/vlooper_test",
        branch_name="main"
    )

@patch("vlooper.agents.git_isolator.clone_repository_workflow")
@patch("vlooper.agents.git_isolator.prepare_repository")
@patch("vlooper.agents.git_isolator.setup_working_branch")
@patch("vlooper.agents.git_isolator.os.path.exists")
@patch("vlooper.agents.git_isolator.os.makedirs")
def test_git_isolator_success(mock_makedirs, mock_exists, mock_setup_branch, mock_prepare_repo, mock_clone, mock_ctx):
    # Setup: Repo doesn't exist, so it will clone
    mock_exists.return_value = False
    mock_clone.return_value = (True, None)
    
    brief = {}
    result = git_isolator_agent(mock_ctx, brief)
    
    assert result["status"] == "success"
    assert result["output"]["workspace_path"].endswith("repo")
    mock_clone.assert_called_once()
    mock_setup_branch.assert_called_once()
    assert mock_ctx.branch_name == "vlooper/fix-123"

@patch("vlooper.agents.git_isolator.clone_repository_workflow")
@patch("vlooper.agents.git_isolator.os.path.exists")
def test_git_isolator_clone_failure(mock_exists, mock_clone, mock_ctx):
    # Setup: Repo doesn't exist, but clone fails
    mock_exists.return_value = False
    mock_clone.return_value = (False, "Network error")
    
    result = git_isolator_agent(mock_ctx, {})
    
    assert result["status"] == "failed"
    assert "Failed to clone repository: Network error" in result["error_message"]

@patch("vlooper.agents.git_isolator.os.path.exists")
@patch("vlooper.agents.git_isolator.prepare_repository")
@patch("vlooper.agents.git_isolator.setup_working_branch")
def test_git_isolator_repo_exists(mock_setup, mock_prepare, mock_exists, mock_ctx):
    # Setup: Repo exists, so it will prepare
    mock_exists.return_value = True
    
    result = git_isolator_agent(mock_ctx, {})
    
    assert result["status"] == "success"
    mock_prepare.assert_called_once()
    mock_setup.assert_called_once()

def test_git_isolator_invalid_url(mock_ctx):
    mock_ctx.repo_url = "invalid-url"
    result = git_isolator_agent(mock_ctx, {})
    assert result["status"] == "failed"

@patch("subprocess.run")
def test_runner_agent_success(mock_run, mock_ctx):
    mock_run.return_value = MagicMock(returncode=0, stdout="Tests passed! No errors.", stderr="")
    result = test_runner_agent(mock_ctx, {})
    assert result["status"] == "success"
    assert result["output"]["exit_code"] == 0
    assert "No significant test failures detected" in result["output"]["logs"]

@patch("subprocess.run")
def test_runner_agent_failure(mock_run, mock_ctx):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="AssertionError: Test failed!")
    result = test_runner_agent(mock_ctx, {})
    assert result["status"] == "failed"
    assert result["output"]["exit_code"] == 1
    assert "AssertionError: Test failed!" in result["output"]["logs"]

@patch("vlooper.services.github_service.clone_repository")
def test_clone_repository_workflow(mock_clone):
    mock_clone.return_value = (True, None)
    success, err = clone_repository_workflow("org/repo", "repo", "/tmp/dir")
    assert success is True
    assert err is None

    mock_clone.return_value = (False, "error")
    success, err = clone_repository_workflow("org/repo", "repo", "/tmp/dir")
    assert success is False
    assert err == "error"

def test_get_issue_number():
    task_issue = {"task_type": "ISSUE", "issue_number": 456}
    assert get_issue_number(task_issue) == "456"

    task_branch = {"task_type": "ISSUE", "branch_name": "fix-789"}
    assert get_issue_number(task_branch) == "789"

    task_pr = {"task_type": "PR"}
    assert get_issue_number(task_pr) == "PR"

@patch("vlooper.services.github_service.post_comment")
def test_post_github_comment(mock_post):
    mock_post.return_value = (None, None)
    task = {"repo_full_name": "org/repo", "task_type": "ISSUE", "issue_number": 123}
    post_github_comment(task, "message")
    mock_post.assert_called_once_with("org/repo", "123", "message")

@patch("vlooper.agents.ai_fixer.OpencodeClient")
@patch("vlooper.agents.ai_fixer.has_uncommitted_changes")
def test_ai_fixer_success(mock_has_changes, mock_client_class, mock_ctx):
    # Case 1: Tests already passing
    brief = {"raw_input": {"status": "success", "output": {"exit_code": 0}}}
    result = ai_fixer_agent(mock_ctx, brief)
    assert result["status"] == "success"
    assert result["output"]["applied"] is False

    # Case 2: Successful fix with changes detected
    mock_client = mock_client_class.return_value
    mock_client.run.return_value = ("", None)
    mock_has_changes.return_value = True
    
    brief = {
        "action": "Fix this",
        "raw_input": {"status": "failed", "output": {"logs": "Some error", "exit_code": 1}}
    }
    result = ai_fixer_agent(mock_ctx, brief)
    assert result["status"] == "success"
    assert result["output"]["applied"] is True

@patch("vlooper.agents.ai_fixer.OpencodeClient")
def test_ai_fixer_client_error(mock_client_class, mock_ctx):
    mock_client = mock_client_class.return_value
    mock_client.run.return_value = ("", "API Error")
    
    brief = {
        "action": "Fix this",
        "raw_input": {"status": "failed", "output": {"logs": "Some error", "exit_code": 1}}
    }
    result = ai_fixer_agent(mock_ctx, brief)
    assert result["status"] == "failed"
    assert result["error_message"] == "API Error"

@patch("vlooper.agents.ai_fixer.OpencodeClient")
@patch("vlooper.agents.ai_fixer.has_uncommitted_changes")
def test_ai_fixer_no_changes(mock_has_changes, mock_client_class, mock_ctx):
    mock_client = mock_client_class.return_value
    mock_client.run.return_value = ("", None)
    mock_has_changes.return_value = False
    
    brief = {
        "action": "Fix this",
        "raw_input": {"status": "failed", "output": {"logs": "Some error", "exit_code": 1}}
    }
    result = ai_fixer_agent(mock_ctx, brief)
    assert result["status"] == "success"
    assert result["output"]["applied"] is False
    assert "no code changes detected" in result["output"]["reason"]

@patch("vlooper.agents.ai_fixer.OpencodeClient")
def test_ai_fixer_critical_exception(mock_client_class, mock_ctx):
    mock_client = mock_client_class.return_value
    mock_client.run.side_effect = Exception("Unexpected crash")
    
    brief = {
        "action": "Fix this",
        "raw_input": {"status": "failed", "output": {"logs": "Some error", "exit_code": 1}}
    }
    result = ai_fixer_agent(mock_ctx, brief)
    assert result["status"] == "failed"
    assert "Unexpected crash" in result["error_message"]
