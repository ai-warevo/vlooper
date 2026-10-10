# Task: Fix Insecure Lock File Creation (Symlink Attack)
**Vulnerability Type:** CWE-377: Insecure Temporary File / CWE-59: Improper Link Resolution before File Operation
**Severity:** High
**Target Files:** `src/vlooper/core/daemon.py`

## Context & Description
The daemon implements process synchronization (locking) using a predictable file path `/tmp/vlooper.lock` and the `fcntl` module. While using a file as an IPC "mutex" is correct for independent processes, the current method of opening the file is vulnerable to a **Symlink Attack**.

By using `open(self.lock_file, "w")`, the application follows any symbolic links existing at that path. A malicious user could create a symlink at `/tmp/vlooper.lock` pointing to a sensitive system file (e.g., `/etc/passwd`). When the daemon starts, it will inadvertently open and potentially overwrite the target system file with high privileges or lock it in an unexpected state.

We must ensure that the fix:
1. Prevents attackers from hijacking the path via symlinks.
2. Still allows the locking mechanism to prevent multiple instances of the daemon from running simultaneously.

## Insecure Code Reference
```python
# Line 57 in src/vlooper/core/daemon.py
self.lock_file = "/tmp/vlooper.lock"

# ... (later)

# Line 124 in src/vlooper/core/daemon.py
with open(self.lock_file, "w", encoding="utf-8") as lock_fd:
```

## Remediation Instruction (Prompt for the Developer Agent)
Act as an expert software engineer. Modify `src/vlooper/core/daemon.py` to securely implement the process lock. 

Follow these strict constraints:
1. **Prevent Symlink Attacks:** Do not use standard `open(path, "w")` on a predictable path in a public directory like `/tmp`. Instead, use one of these two secure approaches:
    * **Option A (Recommended - Private Directory):** Use `tempfile.mkdtemp()` to create a private subdirectory within the system temporary directory. Set this directory's permissions to `0700`. The lock file should reside inside this private directory. This prevents attackers from placing symlinks in the path.
    * **Option B (Atomic Creation):** Use `os.open` with combined flags `os.O_CREAT | os.O_EXCL`. This ensures that the file is created atomically; if a file or symlink already exists at the target path, the operation will fail immediately rather than following the link.
2. **Maintain Multi-Instance Protection:** Ensure that your chosen method still allows the daemon to detect if another instance is already running (e.g., by failing to acquire the lock or failing to create the file/directory).
3. Do not alter the business logic regarding how `fcntl.flock` is used for synchronization.
4. Ensure that after your changes, running the repository's `./test.sh` script passes successfully with an `exit 0` status.

## Expected Secure Code Pattern (Using Option A)
```python
import tempfile
import os
import fcntl

# Inside VLooperDaemon.__init__
self._lock_dir = tempfile.mkdtemp(prefix="vlooper_locks_")
self.lock_file = os.path.join(self._lock_dir, "daemon.lock")

# Inside _lock_context
with open(self.lock_file, "w", encoding="utf-8") as lock_fd:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield lock_fd
    except OSError:
        # Handle error (e.g., another instance is running)
```
