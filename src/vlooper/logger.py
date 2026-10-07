"""Module for configuring and accessing the logger."""

import logging
import sys

from vlooper.config import config


def setup_logging():
    """Configures the global logging settings."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]
    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file))

    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def get_logger(name: str):
    """Returns a logger instance for the given name."""
    return logging.getLogger(name)
