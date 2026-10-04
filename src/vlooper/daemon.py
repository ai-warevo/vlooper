import time
import signal
import sys
import os
import fcntl
from vlooper.database import Database
from vlooper.scanner import Scanner
from vlooper.worker import Worker

class VLooperDaemon:
    def __init__(self):
        self.db = Database()
        self.scanner = Scanner(self.db)
        self.worker = Worker(self.db)
        self.running = True
        self.lock_file = "/tmp/vlooper.lock"

        # Handle termination signals
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        print("\n🛑 Stopping daemon...")
        self.running = False

    def run(self):
        # Attempt to acquire an exclusive lock on the lock file
        lock_fd = open(self.lock_file, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("❌ Another instance of vLooper is already running. Exiting.")
            sys.exit(1)

        print("🚀 vLooper Daemon started with lock acquired.")
        while self.running:
            try:
                # 1. Scan for new tasks
                self.scanner.scan()

                # 2. Check if a worker is already active (as a secondary check)
                active_task = self.db.get_active_claimed_task()
                if active_task:
                    print(f"⏳ A task is already being processed (# {active_task['id']}). Waiting...")
                else:
                    # 3. Process the next pending task
                    success = self.worker.process_next_task()
                    if not success:
                        # No tasks found or error occurred, but we continue loop
                        pass

                # Sleep to avoid hammering everything
                time.sleep(30)

            except Exception as e:
                print(f"⚠️ Unexpected error in daemon loop: {e}")
                time.sleep(10)
        
        lock_fd.close()
        print("👋 Daemon shut down.")

def main():
    daemon = VLooperDaemon()
    daemon.run()

if __name__ == "__main__":
    main()
