# Task 01: Core Infrastructure (MVP)

## Goal
Transform vLooper from a stateless script into a stateful, SQLite-backed daemon that manages tasks through a queue.

## Requirements
- **SQLite Integration**: Implement a database schema to track task lifecycle: `id`, `task_type` (ISSUE/PR), `repo_full_name`, `branch_name`, `status` (PENDING, CLAIMED, COMPLETED, FAILED), `retries`, `last_error`, `created_at`, `updated_at`.
- **Daemon Lifecycle**: 
    1. **Scanner**: Queries GitHub for new issues/PRs and populates the SQLite `PENDING` queue.
    2. **Worker**: Picks up a `PENDING` task, marks it as `CLAIMED`, executes the work, then marks it `COMPLETED` or `FAILED`.
- **Single Worker Constraint**: Ensure only one instance of the worker runs at a time (e.g., via a file lock or checking DB state).
- **Error Handling & Robustness**:
    - Implement a `max_retries` setting (default: 2). If a task fails, increment retries and set back to `PENDING`. 
    - Implement an execution timeout (default: 15s for individual commands) to prevent hanging processes.

## Definition of Done
- A running daemon that can scan, queue, and process one task at a time via SQLite.
- Successfully handles failed tasks through retries.
- Does not crash or overlap if a command hangs (timeout works).
