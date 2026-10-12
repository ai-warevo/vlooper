# Implementation Guide: Phase 6 - Intelligent Orchestration

## Context
Once all core steps have been migrated to agents, we will implement the "Reactive Brain" of vLooper. This phase moves us from a linear execution model to a dynamic, self-healing one.

## Objective
Implement the **Reactive Scheduler** to monitor step outcomes and inject corrective actions based on agent feedback.

## Detailed Tasks

### 1. Reactive Scheduler Implementation
- Develop logic in `src/vlooper/services/scheduler_service.py` (or a new component) that inspects the `output_data` JSON from completed steps.
- If a step returns `{"status": "failed"}` or specific error patterns (e.g., test failure), the scheduler must decide which agent to inject next.

### 2. Error Pattern Mapping
Define specific triggers for corrective steps:
- **Pattern**: `test_runner` output contains `FAILED`. $\rightarrow$ **Action**: Inject `test_healer`.
- **Pattern**: `linter_bot` output contains unresolved errors. $\rightarrow$ **Action**: Inject `ai_fixer`.
- **Pattern**: `pr_reviewer` provides critical feedback. $\rightarrow$ **Action**: Inject `review_fixer`.

### 3. Decision Engine Logic
Ensure the scheduler handles "Recursive Loops" (e.g., testing a fix that leads to another failure) using a retry limit mechanism within the task lifecycle.

## Verification
- Simulate a test failure in the DB and verify that the `test_healer` agent is automatically added as the next step for that Task ID.
