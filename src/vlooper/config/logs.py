import os
from dataclasses import dataclass, field


@dataclass
class LogConfig:
    """Logging related configuration."""

    level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    file: str | None = field(default_factory=lambda: os.environ.get("LOG_FILE", None))
