"""Configuration management for vlooper."""

from dataclasses import dataclass, field

from dotenv import load_dotenv

from .git import GitConfig
from .infra import InfraConfig
from .logs import LogConfig
from .model import ModelConfig
from .timeouts import TimeoutConfig

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Config:
    """Configuration settings loaded from environment variables."""

    git: GitConfig = field(default_factory=GitConfig)
    model_cfg: ModelConfig = field(
        default_factory=ModelConfig
    )  # renamed to avoid collision
    infra: InfraConfig = field(default_factory=InfraConfig)
    logs: LogConfig = field(default_factory=LogConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)


config = Config()
