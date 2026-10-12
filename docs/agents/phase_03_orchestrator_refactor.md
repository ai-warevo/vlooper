# Phase 03: Orchestrator Refactoring (Explicit Control Flow)

## Objective
The core of the refactor. Remove the `EventBus` dependency for task lifecycle notifications and replace it with direct agent orchestration within the `VLooperOrchestrator`.

## Context
Currently, when a task finishes, the orchestrator emits `TASK_FINISHED`. This triggers handlers "magically". We want to replace this "magic" with explicit calls. The Orchestrator will now be the one deciding: "The task is done, now I will call the Notification Agent and then the Telemetry Agent."

## Tasks
1.  **Clean up `VLooperOrchestrator.__init__`**:
    - Remove all `self.event_bus.subscribe(...)` calls related to task lifecycle (e.g., `TaskStatusHandler`, `GitHubNotificationHandler`, etc.).
    - Remove the instantiation of old handlers.
2.  **Implement Explicit Orchestration in `_process_step`**:
    - Locate the logic where a task is determined to be finished (the `else` block after checking if there are more steps).
    - Instead of just calling `self.event_bus.emit(EventName.TASK_FINISHED, ctx)`, implement the sequence of calls:
        1.  Call the new `TaskCompletionAgent`.
        2.  If the result was a PR creation, call the `TelemetryAgent`.
3.  **Remove Unused Imports**: Clean up `orchestrator.py` by removing imports for old handlers and the `EventBus` (if no longer used elsewhere in orchestrator).

## Acceptance Criteria
- [ ] `VLooperOrchestrator` no longer has any code that subscribes to "lifecycle" events via `event_bus`.
- [ ] The flow of a completed task is explicitly visible in the Orchestrator's code (e.g., via direct calls to agents).
- [ ] No regressions in how tasks are marked as COMPLETED or FAILED in the database.
