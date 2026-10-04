#!/usr/bin/env python3
import sys
from vlooper.daemon import VLooperDaemon

if __name__ == "__main__":
    # Ensure GH_TOKEN is set if we rely on it for many commands
    import os
    if "GH_TOKEN" not in os.environ:
        print("⚠️ Warning: GH_TOKEN is not set. Some GitHub operations might fail.")
    
    daemon = VLooperDaemon()
    daemon.run()
