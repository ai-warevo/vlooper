X=5
PHASE_NAME=agent_migration

# Role: Senior Software Engineer / Architect

## Context
We are performing a major architectural evolution of the **vLooper** system. We are moving from a monolithic "Pipeline" architecture to a distributed, **Step-Based Architecture**. 

In this new paradigm:
1.  There are no "manager agents". Orchestration is handled by code (a **Scheduler**).
2.  The core unit of work is an atomic **Step** stored in the `tasks_steps` table.
3.  Each step is executed by a specialized functional **Role**.

## Reference Documents
You MUST read following files before performing any actions:
1.  **Master Specification (Global Architecture):** `docs/subagents/global.md`
2.  **Phase Instructions:** `docs/subagents/phase_[X]_[PHASE_NAME].md` *(Note to user: Replace [X] and [PHASE_NAME] with the current phase number and its name)*

*Optional:*
- **Migration Roadmap:** `docs/subagents/migration_roadmap.md`. Read this if you need context on the overall architectural evolution or if your task is part of a broader migration strategy.

## Your Task
Your goal is to implement **Phase [X]: [PHASE_NAME]**.

### Strict Requirements:
- **Adhere to the Global Spec**: Do not attempt to use or implement any "Pipeline" logic. Everything must be centered around the `tasks_steps` table.
- **Atomic Operations**: Ensure all database operations (especially claiming steps) are atomic and safe for a multi-worker environment.
- **Code Quality**: Use strict type hinting (Python 3.10+), maintain existing project patterns, and ensure all new implementations are documented.
- **No Assumptions**: If the instructions in your phase file conflict with the current implementation or the global spec, ask for clarification before proceeding.

## Expected Output
Follow all requirements and expected outputs specifically described in your assigned phase document (`docs/subagents/phase_[X]_[PHASE_NAME].md`).

**Begin by reading both reference files.**
