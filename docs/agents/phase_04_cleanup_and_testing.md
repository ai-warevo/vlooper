# Phase 04: Cleanup & Final Verification

## Objective
Complete the refactoring by removing all legacy code and ensuring the new explicit orchestration flow is robust and bug-free.

## Context
Phases 1-3 have replaced the reactive event system with an explicit agent-based one. Now we need to remove the "scaffolding" (the old handler files) and run a full verification.

## Tasks
1.  **Delete Legacy Files**:
    - Remove `src/vlooper/core/event_handlers/` (or at least all the handlers that were converted).
    - Ensure no other parts of the codebase are still trying to import from these old files.
2.  **Verify Agent Integration**:
    - Double-check that all utility agents are correctly registered in the `RoleRegistry` or directly available to the Orchestrator.
3.  **End-to-End Testing**: 
    - Verify a "Success with PR" flow: Agent creates PR $\rightarrow$ Orchestrator calls TelemetryAgent $\rightarrow$ Success.
    - Verify a "Failure" flow: Agent fails $\rightarrow$ Orchestrator calls TaskCompletionAgent (to post failure comment) $\rightarrow$ Failure status set.
4.  **Final Code Audit**: 
    - Check for any remaining `event_bus.emit` calls that were intended to be replaced by direct agent calls.

## Acceptance Criteria
- [ ] The directory `src/vlooper/core/event_handlers/` is gone (or contains only non-refactored handlers).
- [ ] The entire cycle from Task Discovery $\rightarrow$ Completion works perfectly without using the `EventBus` for lifecycle notifications.
- [ ] The "link to PR" bug (fixed in previous steps) is verified to still work under the new architecture.
