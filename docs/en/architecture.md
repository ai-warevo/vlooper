# vLooper Project Architecture

<div align="center">

**🇬🇧 English • [🇷🇺 Русский](../ru/architecture.md)**

</div> 

---

The **vLooper** project is a modular, agentic system designed for autonomous task execution (specifically, automated bug fixing in GitHub repositories using AI). 

Unlike traditional linear pipelines, vLooper utilizes a **step-based reactive architecture**. Instead of executing a single monolithic task, the system breaks work down into discrete, trackable steps that can be dynamically re-planned based on real-time feedback.

## Core Architectural Layers

### 1. Discovery & Planning Layer (`Scanner` & `SchedulerService`)
This layer identifies work and defines the initial roadmap.
* **Scanning:** The `Scanner` monitors GitHub for new issues or Pull Requests and persists them to the database.
* **Initial Planning:** Upon finding a task, the `SchedulerService` immediately generates a sequence of atomic steps (e.g., *issue_fetcher* $\rightarrow$ *git_isolator*) required to start the work.
* **Reactive Re-planning:** The "Brain" of the system. If a step fails or returns critical feedback (like test failures), the `SchedulerService` can dynamically inject corrective steps (e.g., *test_healer*, *ai_fixer*) into the current task's queue.

### 2. Execution & Orchestration Loop (`VLooperDaemon`, `RoleRegistry`, `Synthesizer`)
The daemon operates as a continuous consumer of work from the database.
* **Step-Based Processing:** The `VLooperDaemon` runs in an infinite loop, pulling individual **Steps** rather than entire tasks. This allows for high resilience; if a step fails, only that step (or its corrective successor) needs attention.
* **Role Registry:** To ensure loose coupling, agents are not hardcoded. Instead, the `RoleRegistry` maps role identifiers to specific executor functions (e.g., mapping "test_runner" to `test_runner_agent`).
* **Context Synthesis:** The `Synthesizer` prepares high-signal "Mission Briefs" for each agent. It aggregates global task context, current step requirements, and the execution history of all previously completed steps into a single instruction set.

### 3. Data Flow & Step Management (`Database` & `Step Lifecycle`)
The system relies on the database as a shared state and communication bus between agents.
* **Atomic Steps:** Every action is recorded in the `tasks_steps` table, tracking its status (PENDING, RUNNING, COMPLETED, FAILED), inputs, outputs, and errors.
* **Automated Data Injection:** vLooper automatically facilitates data flow by taking the `output_data` of a completed step and injecting it as the `input_data` for the next step in the sequence.

### 4. Persistence Layer (`Database`)
The database acts as the single source of truth, managing:
* **Task States:** High-level status of repositories and issues being worked on.
* **Step Granularity:** A detailed audit trail of every atomic operation performed by any agent.
* **Migrations:** A robust system for evolving the database schema as the project grows.

## Design Patterns Used

| Pattern | Application in vLooper |
| :--- | :--- |
| **Producer-Consumer** | `Scanner` produces tasks $\rightarrow$ `Daemon` consumes atomic steps from the DB. |
| **Reactive Planning** | The system dynamically modifies the task execution plan based on step outcomes. |
| **Registry Pattern** | Decouples role names from their implementations via `RoleRegistry`. |
| **Command / Step Pattern** | Encapsulates every discrete action into a trackable, idempotent database entry. |
| **Synthesizer (Contextualization)** | Aggregates fragmented state/history into coherent instructions for LLM agents. |

## Summary
The vLooper architecture is designed to be **highly resilient**, **massively parallelizable** (multiple daemons can process steps simultaneously), and **intrinsically adaptive** to the unpredictable nature of software debugging.