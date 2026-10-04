import importlib
import os

from vlooper import config as config_module


def test_config_defaults(monkeypatch):
    # Set environment variables to their default values to ensure they are used
    # even if a .env file is present.
    monkeypatch.setenv("ORG_NAME", "ai-warevo")
    monkeypatch.setenv("BOT_USERNAME", "your_bot_login")
    monkeypatch.setenv("MODEL", "ollama/gemma")
    monkeypatch.setenv("TEST_COMMAND", "./test.sh")
    monkeypatch.setenv("DB_PATH", "vlooper.db")
    monkeypatch.setenv("MAX_RETRIES", "2")
    monkeypatch.setenv("EXECUTION_TIMEOUT", "15")
    monkeypatch.setenv("WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace"))

    importlib.reload(config_module)
    c = config_module.config

    assert c.org_name == "ai-warevo"
    assert c.bot_username == "your_bot_login"
    assert c.model == "ollama/gemma"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("ORG_NAME", "custom-org")
    monkeypatch.setenv("BOT_USERNAME", "tester")
    monkeypatch.setenv("MAX_RETRIES", "5")

    importlib.reload(config_module)
    c = config_module.config

    assert c.org_name == "custom-org"
    assert c.bot_username == "tester"
    assert c.max_retries == 5
