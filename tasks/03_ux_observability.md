# Task 03: UX & Observability

## Goal
Provide visibility into the daemon's activities through local TUI and remote GitHub feedback.

## Requirements
- **Local TUI**: Build a lightweight Terminal User Interface (using `curses`, `textual`, or similar) that allows a user to see:
    - Current status of the worker (Idle, Working on Issue #X, etc.).
    - The SQLite queue contents (`PENDING`, `CLAIMED`, `COMPLETED`, `FAILED`).
    - Basic logs.
- **GitHub Feedback Loop**: Automate posting updates to GitHub Issues/PRs:
    - "🤖 vLooper has picked up this task."
    - "🛠️ Attempt 1 failed. Retrying..." 
    - "✅ Task completed! Pull Request created."
    - Summary of changes if a PR was updated based on comments.

## Definition of Done
- A TUI is available that accurately reflects the SQLite database state.
- The bot leaves meaningful, automated comments on GitHub as part of its workflow.
