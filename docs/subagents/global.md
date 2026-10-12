# vLooper: Step-Based Autonomous Architecture (Global Specification)

## 1. Executive Summary
vLooper is an autonomous, step-based system. It decomposes complex GitHub Issues into a sequence of tiny, atomic tasks executed by specialized micro-workers.

## 2. Core Philosophy
- **Pure Atomic Pipeline**: We do not have "manager agents." Instead, we have a code-based **Scheduler (Planner)** that breaks an Issue into a stream of atomic steps.
- **No Reasoning Entropy**: Agents do not plan. They receive a compressed "Mission Brief" from the Synthesizer and execute it blindly.
- **Data-Driven Flow**: Communication happens via JSON payloads in the `tasks_steps` table.

## 3. System Components

### A. The Executor (The Daemon)
Processes the next available step in the queue:
1. Find next `PENDING` step in `tasks_steps`.
2. Retrieve Role execution logic.
3. Generate a "Mission Brief" for that specific role.
4. Execute and record results.

### B. The Brain (The Scheduler & Synthesizer)
- **Scheduler (Planner)**: Analyzes an Issue and pops it into the database as a chain of atomic roles/steps.
- **Reactive Scheduler**: Monitors step failures and injects corrective steps (e.g., if tests fail, inject `test_healer`).
- **Mission Brief Synthesizer**: Compresses history $\rightarrow$ extremely dense "Action Instruction" for the worker.

### C. Data Model
- **`tasks` table**: Represents the high-level Issue/Goal.
- **`tasks_steps` table**: The actual work queue. Each row is an atomic assignment: `[TaskID | Role | Status | InputJSON | OutputJSON]`.

## 4. Agent Roles (The Micro-workers)
| Role | Responsibility |
| :--- | :--- |
| `linter_bot` | Scans/fixes linting and formatting issues |
| `test_healer` | Analyzes failed logs and patches code or tests |
| `coverage_booster` | Writes unit tests to increase coverage |
| `pr_reviewer` | Performs automated code review via GH CLI |
| `review_fixer` | Applies fixes based on PR feedback |
| `github_pr_creator` | Handles the final commit, push, and PR creation |

---
*Reference: This document is the single source of truth for all sub-agent implementations.*
