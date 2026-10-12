# Implementation Guide: Phase 5 - Legacy Step Migration

## Context
This phase focuses on replacing old-style legacy steps with modern, autonomous agents. These agents will follow the new RoleExecutor interface and communicate through structured JSON data in the `tasks_steps` table.

## Objective
Migrate all remaining core functions (`git_isolator`, `issue_fetcher`, `test_runner`, `ai_fixer`) from legacy wrappers to native micro-workers.

## Detailed Tasks

### 1. Agent Implementation (The "Working" part)
For each legacy component, create a new executor in `src/vlooper/agents/[name].py`:
- **`git_isolator_agent`**: Handle repository isolation and return the specific workspace path used.
- **`issue_fetcher_agent`**: Fetch issue details and return them as a structured JSON object.
- **`test_runner_agent`**: Run tests, capture stdout/stderr, and return detailed test results (Pass/Fail + Logs).
- **`ai_fixer_agent`**: Take error logs or linting errors from the brief and apply fixes via OpenCode.

### 2. Schema Standardization
Every agent must output a dictionary with at least:
```json
{
  "status": "success" | "failed",
  "output": { ... },
  "error_message": "..." (optional)
}
```

### 3. Daemon Refactoring
- Remove `wrap_legacy` from `src/vlooper/core/daemon.py`.
- Replace `registry.register(..., wrap_legacy(...))` with native registrations of the new agents.

## Verification
- Unit tests for each agent's JSON output format.
- Integration test: Trigger a sequence where an agent uses the output from another (e.g., `issue_fetcher` $\rightarrow$ `git_isolator`).
