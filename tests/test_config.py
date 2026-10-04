import os
from vlooper.config import Config

def test_config_defaults():
    # Test defaults when no env vars are set
    # We need to be careful since config is initialized at module level.
    # To test different environments, we might need to reload or re-instantiate.
    c = Config()
    assert c.org_name == "ai-warevo"
    assert c.bot_username == "your_bot_login"
    assert c.model == "ollama/gemma"
    assert c.test_command == "./test.sh"

def test_config_env_override(monkeypatch):
    # Test overriding via environment variables
    monkeypatch.setenv("ORG_NAME", "custom-org")
    monkeypatch.setenv("BOT_USERNAME", "tester")
    monkeypatch.setenv("MAX_RETRIES", "5")
    
    # Re-instantiate to pick up new env vars
    c = Config()
    assert c.org_name == "custom-org"
    assert c.bot_username == "tester"
    assert c.max_retries == 5
