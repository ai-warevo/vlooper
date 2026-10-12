# Implementation Guide: Phase 2 - Orchestration & Execution Engine

## Context
This phase implements the core execution engine for the **Pure Atomic Pipeline**, as defined in [global.md](./global.md). We are moving away from monolithic pipelines to a step-by-step worker loop.

## Objective
Refactor the Daemon into a Step-Worker and implement a Role Registry to map roles to atomic functions.

## Detailed Tasks

### 1. Step Registry Implementation (`src/vlooper/core/framework/`)
- Implement a `RoleRegistry` class that maps role strings (e.g., 'linter_bot') to their corresponding Python executor functions.
- Ensure registration occurs during system startup.

### 2. Daemon Refactoring (`src/vlooper/core/daemon.py`)
- **Remove**: The hardcoded `TaskPipeline` construction.
- **New Execution Loop**:
    1.  Poll for the next step using `database.get_next_pending_step()`.
    2.  Retrieve the executor from the `RoleRegistry`.
    3.  Call the **Synthesizer** to prepare a "Mission Brief".
    4.  Execute the role-specific function within a managed context (error handling/logging).
    5.  Update the step's status and `output_data` in the DB.

### 3. Data Flow Mechanism
- Implement logic to facilitate movement of data between steps:
    - The `output_data` of Step $N$ must be injectable as the `input_data` for Step $N+1$.

### 4. Verification
- Mock a task in the DB with a sequence of 3 roles.
- Run the Daemon and verify it processes them sequentially, updating their statuses correctly.
