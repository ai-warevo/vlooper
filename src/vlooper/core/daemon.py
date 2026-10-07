\"\"\"The main daemon process for vLooper.\"\"\"

import fcntl
import signal
import sys
import time
import logging

from vlooper.config import config
from vlooper.core.engine import TaskEngine
from vlooper.core.scanner import Scanner
from vlooper.database import Database
from vlooper.logger import get_logger


logger = get_logger(__name__)


class VLooperDaemon:  # pylint: disable=too-few-public-methods
    \"\"\"The main daemon process for vLooper.\"\"\"

    def __init__(self):
        self.db = Database()
        self.scanner = Scanner(self.db)
        self.engine = TaskEngine(self.db)
        self.running = True
        self.lock_file = \"/tmp/vlooper.lock\"

        # Handle termination signals
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, _signum: int, _frame):
        \"\"\"Handle exit signal.\"\"\"
        logger.info(\"\\n🛑 Stopping daemon...\")
        self.running = False

    def run(self, retry_failed=False):
        \"\"\"Main execution loop.\"\"\"
        logger.debug(f\"Using lock file: {self.lock_file}\")

        # Attempt to acquire an exclusive lock on the lock file
        with open(self.lock_file, \"w\", encoding=\"utf-8\") as lock_fd:
            try:
                logger.debug(\"Attempting to acquire file lock...\")
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(\"Lock acquired successfully.\")
            except OSError:
                logger.error(
                    \"❌ Another instance of vLooper is already running. Exiting.\"
                )
                sys.exit(1)

            logger.info(
                f\"🚀 vLooper Daemon started with lock acquired. (Retry mode: {retry_failed})\"
            )
            while self.running:
                try:
                    # 1. Scan for new tasks
                    self.scanner.scan(retry_failed=retry_failed)

                    # 2. Check if a worker is already active (as a secondary check)
                    active_task = self.db.get_active_claimed_task()
                    if active_task:
                        logger.info(
                            f\"⏳ A task is already being processed (# {active_task['id']}). \"
                            \"Waiting...\"
                        )
                        logger.debug(f\"Active task detected in DB: {active_task}\")
                    else:
                        # 3. Process the next pending task
                        logger.debug(\"No active tasks found from DB check. Attempting to process next.\")
                        self.engine.process_next_task()

                    # Sleep to avoid hammering everything
                    logger.debug(f\"Loop iteration complete. Sleeping for {config.loop_sleep_seconds}s...\")
                    time.sleep(config.loop_sleep_seconds)

                except Exception as e:  # noqa: W0718
                    logger.error(f\"⚠️ Unexpected error in daemon loop: {e}\")
                    logger.debug(\"Sleeping for error recovery period...\")
                    time.sleep(config.error_wait_seconds)

        logger.info(\"👋 Daemon shut down.\")


def main(retry_failed=False):
    \"\"\"Entry point for the daemon.\"\"\"
    daemon = VLooperDaemon()
    daemon.run(retry_failed=retry_failed)


if __name__ == \"__main__\":
    main()
