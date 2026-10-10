from dataclasses import dataclass, field
import os
from typing import Optional

@dataclass
class ModelConfig:
    """Model related configuration."""
    model: str = field(
        default_factory=lambda: os.environ.get("MODEL", "ollama/gemma")
    )
    alt_model: Optional[str] = field(
        default_factory=lambda: os.environ.get("_MODEL", None)
    )
