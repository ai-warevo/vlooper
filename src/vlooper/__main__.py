#!/usr/bin/env python3
"""Module documentation."""

import argparse
import os
import sys

try:
    from vlooper.core.daemon import VLooperDaemon
except ImportError as exc:
    raise ImportError(
        "Could not import VLooperDaemon. "
        "Ensure you are running from the project root."
    ) from exc

from vlooper.infra.logger import get_logger, setup_logging

logger = get_logger(__name__)


def get_tui_class() -> type | None:
    """Returns the TUI class if available."""
    try:
        # pylint: disable=import-outside-toplevel
        from vlooper.ui.tui import VLooperTUI

        return VLooperTUI
    except ImportError:
        return None


def main(argv=None):
    """Main entry point for the vLooper daemon."""
    setup_logging()
    parser = argparse.ArgumentParser(description="vLooper Daemon")
    parser.add_argument("--tui", action="store_true", help="Run the TUI dashboard")
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry failed tasks from database"
    )
    args = parser.parse_args(argv)

    if args.tui:
        v_tui_class = get_tui_class()
        if v_tui_class is None:
            logger.error("TUI module not found.")
            sys.exit(1)
        app = v_tui_class()
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
