import os
from dataclasses import dataclass, field


@dataclass
class InfraConfig:
    """Infrastructure related configuration."""

    test_command: str = field(
        default_factory=lambda: os.environ.get("TEST_COMMAND", "./test.sh")
    )
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "vlooper.db")
    )
    workspace_base_dir: str = field(
        default_factory=lambda: os.environ.get(
            "WORKSPACE_BASE_DIR", os.path.expanduser("~/ai_agent/workspace")
        )
    )
