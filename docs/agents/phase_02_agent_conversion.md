# Phase 02: Agent Conversion (Handlers $\rightarrow$ Agents)

## Objective
Convert existing, passive `EventHandlers` into active, specialized `Agents` that follow the new unified interface.

## Context
We have several handlers in `src/vlooper/core/event_handlers/` that currently wait for events. We need to move their logic into new agent files and prepare them to be called directly.

## Tasks
1.  **Create `TaskCompletionAgent`**:
    - Move logic from `GitHubNotificationHandler` to `src/vlooper/agents/utility/task_completion_agent.py`.
    - This agent handles posting success (non-PR) or failure comments to GitHub.
2.  **Create `TelemetryAgent`**:
    - Move logic from `PrCreatedHandler` to `src/vlooper/agents/utility/telemetry_agent.py`.
    - This agent handles logging/telemetry when a PR is created.
3.  **Refactor Logic for Explicit Execution**:
    - Ensure both agents use the standard `.execute(ctx: TaskContext)` method defined in Phase 01.
    - Move any necessary imports (like `post_github_comment`) into these new agent files.

## Acceptance Criteria
- [ ] `src/vlooper/agents/utility/task_completion_agent.py` exists and implements the standard interface.
- [ ] `src/vlooper/agents/utility/telemetry_agent.py` exists and implements the standard interface.
- [ ] The logic is functionally identical to the old handlers, but it no longer relies on an internal `handle(ctx)` method or event discovery.
