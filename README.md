# 🔄 vLooper

<div align="center">

**🇬🇧 English • [🇷🇺 Русский](./docs/ru/README.md)**

</div> 

---

**vLooper** is a lightweight local automation orchestrator (Loop & Harness Engineering) that transforms the **Ollama + OpenCode** stack into an autonomous AI developer for GitHub organizations.

It scans organization-wide issues/PRs, pulls repositories locally, and runs a continuous "Write -> Test -> Fix" loop using `OpenCode` until the task is solved and a Pull Request is created.

---

## 🎯 How it Works (Agentic Git-Flow)

1.  **Trigger:** Create an Issue or PR in your organization and assign it to the bot.
2.  **Discovery & Planning:** The `Scanner` identifies new tasks via GitHub CLI (`gh`). For each task, the `SchedulerService` immediately generates a sequence of atomic steps (e.g., *issue_fetcher* $\rightarrow$ *git_isolator*) stored in the database.
3.  **Execution Loop:** The `Orchestrator` continuously pulls individual **Steps** from the DB. It identifies the correct agent via the `RoleRegistry` and executes it using a context-rich "Mission Brief" provided by the `Synthesizer`.
4.  **Reactive Re-planning:** If a step fails (e.g., tests fail or linter errors are found), the `SchedulerService` can dynamically inject corrective steps (like *test_healer* or *ai_fixer*) into the task's queue to resolve the issue.
5.  **Deliver:** Once all scheduled steps are completed successfully, the bot commits and pushes the branch, creating an automated **Pull Request**.

---

## 📚 Documentation

* [Project Architecture](./docs/en/architecture.md)

---

## 🛠 Requirements

*   **Python 3.10+** (managed via `uv`)
*   **Ollama** (with a model like `gemma` running)
*   **OpenCode CLI**
*   **GitHub CLI (`gh`)** with appropriate permissions

---

## 🚀 Quick Start

### 1. Installation & Setup
Clone the repository and install the environment using `uv`:

```sh
# Install dependencies and the project
uv sync

# Set up your GitHub Token (required)
export GH_TOKEN=your_bot_token_here
```

### 2. Running the Orchestrator
To start the core engine that scans and processes tasks:

```sh
uv run vlooper
```

*Alternatively, run from source:* `python -m vlooper`

---

### 🛠 Specialized Commands

**Retry Failed Tasks**  
Instead of scanning GitHub for new tasks, specifically targets failed tasks in the local database. Useful after you've patched a bug that caused previous failures!

```sh
uv run vlooper-retry
```

**Monitoring (TUI Dashboard)**  
To see what the agent is doing in real-time with a beautiful terminal interface, **open a second terminal** and run:

```sh
uv run vlooper-tui
```
*Note: The TUI is only a viewer. You must have the orchestrator running in a separate window to see any activity.*

---

## 🛠 Development Commands

Use these commands to maintain code quality and run tests during development:

| Command | Description |
| :--- | :--- |
| `uv run check` | Run linters and formatters |
| `uv run analyze` | Identify unused files and definitions |
| `uv run pytest` | Execute the test suite |
| `uv sync` | Synchronize local environment with `pyproject.toml` |

---

## ⚠️ Important Notes

*   **The Harness (Test Command):** For the loop to work, every repository must have a `./test.sh` in its root. This script should return `exit 0` on success and `exit 1` on failure.
*   **Feedback Loop:** If you leave comments on a Pull Request, the bot will pick them up on its next scan and attempt to apply your requested changes!