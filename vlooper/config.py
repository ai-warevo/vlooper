import os
from dataclasses import dataclass

@dataclass
class Config:
    org_name: str = os.environ.get("ORG_NAME", "ai-warevo")
    bot_username: str = os.environ.get("BOT_USERNAME", "your_bot_login") # User should set this via env
    model: str = os.environ.get("MODEL", "ollama/gemma")
    test_command: str = os.environ.get("TEST_COMMAND", "./test.sh")
    db_path: str = os.environ.get("DB_PATH", "vlooper.db")
    max_retries: int = int(os.environ.get("MAX_RETRIES", "2"))
    execution_timeout: int = int(os.environ.get("EXECUTION_TIMEOUT", "15"))
    workspace_base_dir: str = os.environ.get("WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace"))

config = Config()
