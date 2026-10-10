# vLooper Project Architecture

<div align="center">

**🇷🇺 Русский • [🇬🇧 English](../ru/architecture.md)**

</div> 

---

The **vLooper** project is a modular, event-driven system with a multi-layered structure designed for autonomous task execution (specifically, automated bug fixing in GitHub repositories using AI).

The system design can be characterized as a combination of the **Pipeline**, **Middleware/Onion**, and **Observer (Event Bus)** patterns.

## Core Architectural Layers

### 1. Orchestration Layer (`VLooperDaemon`)
This is the system's control center. The daemon runs in an infinite loop, performing the following functions:
* **Scanning:** Uses a `Scanner` to search for new tasks in the database or via external APIs.
* **Lifecycle Management:** Retrieves tasks, marks them as "claimed," and initiates execution.
* **Isolation:** Ensures only one instance of the daemon is running using file locking (`fcntl.flock`).

### 2. Execution Engine (`TaskPipeline` & Middleware)
Instead of hardcoded logic, vLooper uses a flexible task processing pipeline:
* **Middleware (Onion Layers):** Wrappers around the core process. They handle cross-cutting concerns such as global exception handling (`GlobalExceptionHandlerMiddleware`), authentication checks, and retry limit control (`RetryLimitMiddleware`).
* **Steps:** Sequential atomic operations executed within a protected context:
    1. Environment setup (`git_isolate_repository`).
    2. Running the test harness (`run_repository_tests`).
    3. Applying AI fixes (`apply_ai_fix`).
    4. Creating a Pull Request (`github_create_pull_request`).

### 3. Event Layer (`EventBus` & Handlers)
To ensure loose coupling, an event bus is utilized. This allows the separation of core execution logic from side effects:
* **Events:** When something significant happens (a task is picked up, tests pass, a PR is created), an event is emitted (e.g., `EventName.TASK_FINISHED`).
* **Handlers:** Components subscribed to the bus react to these events. For example, the `GitHubNotificationHandler` sends notifications, while the `TaskStatusHandler` updates the database status. This enables adding new system reactions without modifying the pipeline code itself.

### 4. Services and Clients Layer (`services/` & `clients/`)
There is a clear separation of responsibilities:
* **Clients:** Low-level tools for direct interaction with external APIs (Git, GitHub, OpenCode).
* **Services:** High-level business logic that orchestrates the work of clients (e.g., `ai_service` manages interactions with the language model).

### 5. Persistence Layer (`persistence/`)
Used for storing task states and execution history. It includes a database migration system, ensuring data schema evolution without information loss.

## Design Patterns Used

| Pattern | Application in vLooper |
| :--- | :--- |
| **Daemon** | A background process continuously monitoring external task sources. |
| **Pipeline / Interceptor** | Sequential task processing through a chain of steps and middleware. |
| **Observer (Event Bus)** | Decoupling execution logic from notification systems and DB updates. |
| **Layered Architecture** | Clear separation: UI $\rightarrow$ Daemon $\rightarrow$ Services $\rightarrow$ Clients $\rightarrow$ Infra/DB. |
| **Strategy / Step** | Encapsulating each stage of work (tests, fix, PR) into a separate callable object. |

## Summary
The architecture is designed to be **highly extensible** (easily adding new steps or event handlers) and **resilient** (thanks to error-handling middleware layers and retry mechanisms). The system is well-suited for complex, long-running automated processes.
