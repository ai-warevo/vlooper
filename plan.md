# Plan: Improving AI Fixer Robustness and Context Filtering in vLooper

## Problem Statement
The `vlooper` orchestrator incorrectly handles task failures when the test runner output contains significant "noise" (e.g., linting errors from unrelated files). Specifically, the `ai_fixer` agent:
1. Gets overwhelmed by irrelevant error messages (linting/style warnings) that are not related to the core issue.
2. Reports a successful execution (`applied: true`) even when no meaningful code changes were made or when the underlying bug persists.

## Objective
Ensure the `ai_fixer` agent focuses on the primary discrepancy reported in the task and provide a reliable mechanism for verifying that code changes actually address the problem.

---

## Phase 1: Deep Dive & Root Cause Analysis (RCA)

### 1.1 Analyze `ai_fixer` Agent Logic
- **Goal**: Understand how `ai_fixer.py` processes mission requirements and executes commands.
- **Action**: Examine `src/vlooper/agents/ai_fixer.py`. Determine if it uses a heuristic for "success" that relies on command exit codes rather than actual effect (file diffs or test passes).

### 1.2 Analyze Context Synthesis
- **Goal**: Understand why the agent receives linting noise instead of just the relevant bug info.
- **Action**: Examine `src/vlooper/core/framework/synthesizer.py` and the `orchestrator`. Trace how the output of `test_runner` is passed to the next step in the pipeline.

---

## Phase 2: Implementation of Component Fixes

### 2.1 Implement Log Filtering (Noise Reduction)
- **Goal**: Prevent "log flooding" from reaching the LLM.
- **Action**: 
    - Create or improve a utility (e.g., in `src/vlooper/infra/utils.py`) to parse test logs.
    - The filter should prioritize:
        1. Test failures (e.g., "AssertionError", "Test Failed").
        2. Errors specifically related to the target repository or logic files.
    - De-prioritize/strip: Pylint/Ruff warnings, trailing whitespace issues, and imports in unrelated test files.

### 2.2 Refine Agent Mission Briefs
- **Goal**: Improve instruction clarity.
- **Action**: Modify the synthesizer to explicitly instruct the agent to ignore style/linting warnings if a functional error is present, or provide a clear priority list (Functional Bug > Style Issue).

### 2.3 Strengthen Success Verification
- **Goal**: Eliminate false positive "success" reports.
- **Action**:
    - Modify the `ai_fixer` step return value logic.
    - A step should only be marked as `success` with `applied: true` if:
        - A file diff is detected OR
        - The specific test command that failed previously now passes.

---

## Phase 3: Verification

### 3.1 Regression Test Case
- **Goal**: Prove the fix works using the exact scenario that caused the failure.
- **Action**:
    1. Re-create the `math_logic.py` bug in a controlled environment (like the `vlooper-test-lab`).
    2. Run `vlooper` with the heavily noisy test environment.
    3. Verify that:
        - The agent ignores the linting noise.
        - The agent fixes the subtraction/addition bug.
        - The orchestration flow completes with a successful PR creation attempt *only after* tests pass.

## Success Criteria
- `ai_fixer` correctly identifies and fixes functional bugs despite high amounts of non-relevant Pylint/Ruff noise in logs.
- No false "success" statuses are reported when the code remains unchanged or broken.
