# vLooper Project Restructuring Plan

This document outlines the plan to consolidate the package structure of `vlooper` to reduce directory fragmentation and group related logic more effectively.

## 🎯 Objective
Reduce the number of sub-packages (currently `agent`, `git`, `github`, `processing`) and instead use broader, logical groupings (`core`, `integrations`, `ui`).

## 🛠 Proposed New Structure

```text
src/vlooper/
├── core/                 # Orchestration & Business Logic
│   ├── __init__.py
│   ├── engine.py         (from src/vlooper/core/engine.py)
│   ├── models.py         (from src/vlooper/core/models.py)
│   ├── loop.py           (from src/vlooper/agent/loop.py)
│   ├── scanner.py        (from src/vlooper/scanner.py)
│   ├── daemon.py         (from src/vlooper/daemon.py)
│   ├── exceptions.py     (from src/vlooper/exceptions.py)
│   └── error_handler.py  (from src/vlooper/processing/error_handler.py)
├── integrations/         # External API & Tool Clients
│   ├── __init__.py
│   ├── git_manager.py    (from src/vlooper/git/manager.py)
│   ├── github_interaction.py (from src/vlooper/github/interaction.py)
│   └── github_client.py  (from src/vlooper/github_client.py)
├── ui/                   # User Interfaces
│   ├── __init__.py
│   └── tui.py            (from src/vlooper/tui.py)
├── config.py             (remains in root)
├── database.py           (remains in root)
├── utils.py              (remains in root)
├── __init__.py           (remains in root)
└── py.typed              (remains in root)
```

## 📋 Implementation Steps

### Phase 1: Setup & File Migration
- [ ] Create new directories: `src/vlooper/core`, `src/vlooper/integrations`, `src/vlooper/ui`.
- [ ] Add `__init__.py` to each new directory.
- [ ] Move files according to the proposed structure:
    - **To `core/`**: `agent/loop.py` $\to$ `core/loop.py`, `scanner.py` $\to$ `core/scanner.py`, `daemon.py` $\to$ `core/daemon.py`, `exceptions.py` $\to$ `core/exceptions.py`, `processing/error_handler.py` $\to$ `core/error_handler.py`.
    - **To `integrations/`**: `git/manager.py` $\to$ `integrations/git_manager.py`, `github/interaction.py` $\to$ `integrations/github_interaction.py`, `github_client.py` $\to$ `integrations/github_client.py`.
    - **To `ui/`**: `tui.py` $\to$ `ui/tui.py`.
- [ ] Delete old empty/unnecessary directories: `agent/`, `git/`, `github/`, `processing/`.

### Phase 2: Import Refactoring
*Crucial step: Every file must be updated to use the new import paths.*

- [ ] **Update Root Files**:
    - `src/vlooper/__init__.py`: Update imports for `AILoop`, `Database`, `VLooperError`, etc.
    - `src/vlooper/daemon.py`: Update imports for `config`, `TaskEngine`, `Database`, `Scanner`.
    - `src/vlooper/scanner.py`: Update imports for `config`, `Database`, `build_gh_view_cmd`, `run_command`.
- [ ] **Update Core Files**:
    - `src/vlooper/core/engine.py`: Update all relative and absolute imports (especially `git_manager`, `interaction`, `error_handler`).
    - `src/vlooper/core/loop.py`: Check if it needs new imports.
- [ ] **Update Integration Files**:
    - `src/vlooper/integrations/github_interaction.py`: Update `run_command` import to `vlooper.utils`.
    - `src/vlooper/integrations/git_manager.py`: Check imports.
- [ ] **Update UI Files**:
    - `src/vlooper/ui/tui.py`: Update `Database` import.

### Phase 3: Validation
- [ ] Check for any remaining broken absolute imports in the codebase.

## ⚠️ Risks & Notes
- **Broken Imports**: This is high risk; automated search/replace or careful manual updates will be needed.
- **Circular Dependencies**: Moving files might expose circular dependencies that were previously hidden by folder boundaries.
- **Tooling**: Any `pyproject.toml` or `setup.py` (if present) needs to be updated if they explicitly mention certain module paths.
