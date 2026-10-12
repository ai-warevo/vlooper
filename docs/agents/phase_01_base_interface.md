# Phase 01: Base Interface & Agent Contract

## Objective
Establish a unified, predictable interface for all "Active Agents" to ensure the Orchestrator can manage them without knowing their internal implementation.

## Context
Currently, vLooper uses `EventHandlers` that react to events on an `EventBus`. We are moving towards a model where specialized agents perform these side effects and are called **explicitly** by the Orchestrator. To do this, every "side-effect agent" must follow the same contract.

## Tasks
1.  **Define the Agent Interface**: 
    - Ensure there is a clear, standardized way for an agent to be invoked. 
    - Recommendation: Create or use a `BaseAgent` abstract class (if appropriate) or simply ensure all specialized agents implement a standard `.execute(ctx: TaskContext) -> None` method.
2.  **Standardize Input/Output**: 
    - All agents must accept the `TaskContext` object as their primary input to ensure they have access to repo info, branch names, and metadata.
3.  **Prepare Registry Support**: 
    - Ensure the `RoleRegistry` can hold these specialized "utility" agents alongside the main worker agents.

## Acceptance Criteria
- [ ] There is a documented convention/interface for all new utility agents.
- [ ] A "dummy" or template agent is created to demonstrate how to implement this interface correctly.
- [ ] The `TaskContext` is confirmed as the single source of truth passed between Orchestrator and Agents.
