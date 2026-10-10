#!/usr/bin/env python3
import argparse
import os
import sys

try:
    from vlooper.core.daemon import VLooperDaemon
except ImportError:
    raise ImportError(
        "Could not import VLooperDaemon. Ensure you are running from the project root or have installed the package."
    )

try:
    from vlooper.ui.tui import VLooperTUI
except ImportError:
    VLooperTUI = None

from vlooper.infra.logger import get_logger, setup_logging

logger = get_logger(__name__)


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="vLooper Daemon")
    parser.add_argument("--tui", action="store_true", help="Run the TUI dashboard")
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry failed tasks from database"
    )
    args = parser.parse_args(argv)

    if args.tui:
        if VLooperTUI is None:
            logger.error("TUI module not found.")
            sys.exit(1)
        app = VLooperTUI()
        app.run()
        return

    # Standard Daemon execution
    if "GH_TOKEN" not in os.environ:
        logger.warning(
            "Warning: GH_TOKEN is not set. Some GitHub operations might fail."
        )

    daemon = VLooperDaemon()
    daemon.run(retry_failed=args.retry_failed)


def main_tui():
    """Entry point specifically for the TUI dashboard."""
    main(["--tui"])


def main_retry():
    """Entry point specifically for retrying failed tasks."""
    main(["--retry-failed"])


if __name__ == "__main__":
    main()
