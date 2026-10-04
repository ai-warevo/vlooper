#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path

# Support src layout for local execution
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from vlooper.daemon import VLooperDaemon
except ImportError:
    # Fallback if running as installed package
    from vlooper.daemon import VLooperDaemon

try:
    from vlooper.tui import VLooperTUI
except ImportError:
    VLooperTUI = None

def main():
    parser = argparse.ArgumentParser(description="vLooper Daemon")
    parser.add_argument("--tui", action="store_true", help="Run the TUI dashboard")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed tasks from database")
    args = parser.parse_args()

    if args.tui:
        if VLooperTUI is None:
            print("❌ TUI module not found.")
            sys.exit(1)
        app = VLooperTUI()
        app.run()
        return

    # Standard Daemon execution
    if "GH_TOKEN" not in os.environ:
        print("⚠️ Warning: GH_TOKEN is not set. Some GitHub operations might fail.")
    
    daemon = VLooperDaemon()
    daemon.run(retry_failed=args.retry_failed)

if __name__ == "__main__":
    main()
