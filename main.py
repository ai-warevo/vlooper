#!/usr/bin/env python3
import sys
import os
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
    if "--tui" in sys.argv:
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
    daemon.run()

if __name__ == "__main__":
    main()
