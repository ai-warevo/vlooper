# Implementation Guide: Phase 1 - Data Layer Evolution

## Context
This phase is part of the transition to the **Pure Atomic Pipeline** architecture, as defined in [global.md](./global.md). We are moving from a single task record to a granular step-based execution model.

## Objective
Prepare the database schema and API to support atomic steps, role-based assignment, and data flow between steps via JSON.

## Detailed Tasks

### 1. Database Schema Expansion (Migrations)
- **Migration 002: Update Tasks Table**
    - Add `meta` column (TEXT or JSON) to the existing `tasks` table for storing high-level context or original issue intent.
- **New Migration: Create Steps Table**
    - Implement `tasks_steps` table with fields:
        - `id` (PK, Auto-increment)
        - `task_id` (FK to tasks.id)
        - `role` (TEXT - the specific micro-worker identifier)
        - `status` (ENUM/TEXT: PENDING, RUNNING, COMPLETED, FAILED)
        - `order_index` (INT - execution sequence)
        - `input_data` (JSON - context/payload for the step)
        - `output_data` (JSON - results produced by the step)
        - `error` (TEXT - error messages or stack traces)

### 2. Database API Refactoring (`src/vlooper/persistence/database.py`)
- **Step Orchestration Methods**:
    - `get_next_pending_step() -> StepDict | None`: Must implement atomic "claim" logic (transitioning from PENDING $\rightarrow$ RUNNING) using `order_index` to maintain sequence.
    - `complete_step(step_id, output_data) -> None`.
    - `fail_step(step_id, error_msg) -> None`.

### 3. Verification
- [ ] Run migrations and ensure no regression in existing task functionality.
- [ ] Test script: Create a Task $\rightarrow$ Generate 3 Steps $\rightarrow$ Retrieve them via the new API.
