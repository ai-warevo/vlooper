# Implementation Guide: Phase 3 - Intelligence (Scheduler & Synthesizer)

## Context
This phase implements the "Brain" of the system as defined in [global.md](./global.md). This is what differentiates a mere executor from an autonomous agentic system.

## Objective
Implement the logic for generating initial step sequences, reacting to failures, and condensing context into high-density instructions (Mission Briefs).

## Detailed Tasks

### 1. The Scheduler Service (`src/vlooper/services/scheduler_service.py`)
- **Initial Planning**: Analyzes a new Issue/Task and generates an initial sequence of Roles in `tasks_steps`.
- **Reactive Re-planning**: Monitors step completions. If a step fails or produces specific output (e.g., test failure), the Scheduler must dynamically inject corrective steps into the queue (e.g., injecting `test_healer` after a failed `run_tests`).

### 2. The Mission Brief Synthesizer (`src/vlooper/core/framework/synthesizer.py`)
- **Logic**: Crucial for token economy and preventing "Reasoning Entropy."
- **Process**: Takes [Global Goal + Step History + Current Step Requirements] and compresses it into a single, extremely dense System Prompt (The "Mission Brief").
- **Target Format**: A high-signal, low-noise instruction set that tells the agent *exactly* what to do right now without making them think about the whole project.

### 3. Verification
- Test Scheduler: Simulate a failed test step and verify that the Scheduler correctly adds a `test_healer` step to the DB.
- Test Synthesizer: Validate that the generated "Mission Brief" is highly focused and avoids redundant history.
