"""Configuration management for vlooper."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Config:
    """Configuration settings loaded from environment variables."""
    org_name: str = field(
        default_factory=lambda: os.environ.get("ORG_NAME", "ai-warevo")
    )
    bot_username: str = field(
        default_factory=lambda: os.environ.get("BOT_USERNAME", "your_bot_login")
    )
    model: str = field(default_factory=lambda: os.environ.get("MODEL", "ollama/gemma"))
    test_command: str = field(
        default_factory=lambda: os.environ.get("TEST_COMMAND", "./test.sh")
    )
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "vlooper.db")
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("MAX_RETRIES", "2"))
    )
    execution_timeout: int = field(
        default_factory=lambda: int(os.environ.get("EXECUTION_TIMEOUT", "15"))
    )
    workspace_base_dir: str = field(
        default_factory=lambda: os.environ.get(
            "WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace")
        )
    )


config = Config()
