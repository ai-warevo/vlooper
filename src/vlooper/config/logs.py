from dataclasses import dataclass, field
import os
from typing import Optional

@dataclass
class LogConfig:
    """Logging related configuration."""
    level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )
    file: Optional[str] = field(
        default_factory=lambda: os.environ.get("LOG_FILE", None)
    )
