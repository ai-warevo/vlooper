import os
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Model related configuration."""

    model: str = field(default_factory=lambda: os.environ.get("MODEL", "ollama/gemma"))
    alt_model: str | None = field(
        default_factory=lambda: os.environ.get("_MODEL", None)
    )
