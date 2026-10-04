# 🔄 vLooper

**vLooper** is a lightweight local automation daemon (Loop & Harness Engineering) that transforms the **Ollama + OpenCode** stack into an autonomous AI developer for GitHub organizations.

It scans organization-wide issues/PRs, pulls repositories locally, and runs a continuous "Write -> Test -> Fix" loop using `OpenCode` until the task is solved and a Pull Request is created.

---

## 🎯 How it Works (AI Git-Flow)

1.  **Trigger:** Create an Issue or PR in your organization and assign it to the bot.
2.  **Scan:** The daemon identifies new tasks via GitHub CLI (`gh`).
3.  **Isolate:** The worker clones the repo into a local workspace and creates a dedicated branch.
4.  **The Loop (Harness):** 
    *   `OpenCode` generates code changes.
    *   The worker runs your `./test.sh`.
    *   If tests fail, the error logs are fed back to the agent to trigger an automatic fix.
5.  **Deliver:** Once tests pass, the bot commits and pushes the branch, creating an automated **Pull Request**.

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

### 2. Running the Daemon
To start the daemon (the engine that scans and processes tasks):

```sh
# Run the core engine in a dedicated terminal
uv run main.py
```

### 3. Monitoring (TUI Dashboard)
To see what the agent is doing in real-time with a beautiful terminal interface, **open a second terminal** and run:

```sh
# Launch the local TUI dashboard in another terminal
uv run main.py --tui
```
*Note: The TUI is only a viewer. You must have the daemon running in a separate window to see any activity.*


---

## 🛠 Development Commands

Use these commands to maintain code quality and run tests during development:

| Command | Description |
| :--- | :--- |
| `uv run check` | Run linters, type checkers, and formatters |
| `uv run pytest` | Execute the test suite |
| `uv sync` | Synchronize local environment with `pyproject.toml` |

---

## ⚠️ Important Notes

*   **The Harness (Test Command):** For the loop to work, every repository must have a `./test.sh` in its root. This script should return `exit 0` on success and `exit 1` on failure.
*   **Feedback Loop:** If you leave comments on a Pull Request, the bot will pick them up on its next scan and attempt to apply your requested changes!