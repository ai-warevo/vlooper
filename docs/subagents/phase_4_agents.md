# Implementation Guide: Phase 4 - Micro-worker Implementation

## Context
This phase involves implementing the actual specialized logic for each role defined in [global.md](./global.md). Each worker is an atomic function designed to work with a "Mission Brief".

## Objective
Develop 6 specialized, low-latency executors.

## Detailed Tasks

### 1. Maintenance & Coverage Agents
- **`linter_bot`**: Uses linters (e.g., ruff) to find errors and applies fixes via OpenCode.
- **`coverage_booster`**: Analyzes coverage reports and generates unit tests via LLM.

### 2. Healing & Feedback Agents
- **`test_healer`**: Parses test error logs, identifies the root cause, and patches the code/tests.
- **`review_fixer`**: Reads PR comments from GitHub and applies requested refinements.

### 3. Review & Lifecycle Agents
- **`pr_reviewer`**: Performs automated code review/audit using LLM on git diffs.
- **`github_pr_creator`**: Commits changes, pushes branches, and opens the final Pull Request via `gh`.

### 4. Verification
- Test each agent in isolation by manually triggering a step with its specific role via the DB.
- Ensure all agents strictly follow their "Mission Brief" and do not attempt tasks outside their scope.
