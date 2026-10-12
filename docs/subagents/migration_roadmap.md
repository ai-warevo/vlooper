# Plan: Legacy Step to Agent Migration

## Objective
Complete the architectural transition of vLooper from a hybrid system (legacy steps + new agents) to a pure, distributed, step-based architecture where every unit of work is an intelligent micro-worker agent.

## Target Milestones

### Phase 5: Core Component Migration
**Goal**: Transform all remaining legacy "steps" into specialized "agents".
*   **Targets**: `git_isolator`, `issue_fetcher`, `test_runner`, and `ai_fixer`.
*   **Actions**:
    1.  Implement new agent modules in `src/vlooper/agents/`.
    2.  Define standard JSON Input/Output schemas for each migrated component.
    3.  Refactor `VLooperDaemon` to remove all usage of `wrap_legacy`.
    4.  Register all components as native `RoleExecutors`.

### Phase 6: Intelligent Orchestration (The Reactive Brain)
**Goal**: Implement the logic that makes the system truly autonomous and reactive.
*   **Actions**:
    1.  Develop the **Reactive Scheduler** which monitors step outcomes.
    2.  Implement "Corrective Injection": automatically inject a `test_healer` agent if a `test_runner` agent returns a `FAILED` status in its JSON output.
    3.  Enhance the `Synthesizer` to create "Success Paths" and "Error Recovery Paths".

### Phase 7: Refined Synthesis & Context Management
**Goal**: Optimize the information density sent to agents to prevent reasoning fatigue and token waste.
*   **Actions**:
    1.  Implement **Context Compression**: A logic layer that summarizes the history of completed steps into a very dense "Mission Brief".
    2.  Optimize the `TaskContext` to handle larger codebases via intelligent file-filtering/chunking.

## Definition of Done (DoD)
*   `src/vlooper/core/daemon.py` contains zero instances of `wrap_legacy`.
*   The `tasks_steps` table is the sole source of truth for all task progress and inter-agent communication.
*   All agents return structured JSON rather than relying on side effects alone.
