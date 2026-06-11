# VS Code Settings Sync Profiles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** planned
**Created:** 2026-06-11
**Completed:** —
**PR:** —

**Goal:** Configure a lightweight, cloud-synced VS Code setup using three isolated Profiles for web/full-stack, systems programming, and AI/ML work.

**Architecture:** Use VS Code built-in Settings Sync as the cloud source of truth. Keep personal editor defaults in the Default Profile, isolate heavyweight language services into dedicated Profiles, and let repository `.vscode/` files remain project-specific when needed.

**Tech Stack:** VS Code Settings Sync, VS Code Profiles, VS Code extension recommendations, GitHub or Microsoft account sync.

---

## Confirmed Decision

Use **VS Code Settings Sync only** for cloud synchronization. Do not introduce a dotfiles repository for this task.

## Sync Scope

Enable these Settings Sync categories:

- Settings
- Keyboard Shortcuts
- User Snippets
- User Tasks
- Extensions
- Profiles

Do not sync UI state or workspace state. These values are machine- and session-specific, and syncing them across devices usually creates noisy window layout and recent-file churn.

## Profile Strategy

### Default Profile

Purpose: shared editor baseline and cross-scenario tools.

Recommended extensions:

- `eamodio.gitlens` — GitLens
- `ms-azuretools.vscode-docker` — Docker
- `ms-vscode-remote.remote-ssh` — Remote SSH
- `github.copilot` — GitHub Copilot, if preferred
- `continue.continue` — Continue, if preferred

Recommended baseline settings:

```json
{
  "editor.fontSize": 14,
  "editor.lineHeight": 22,
  "editor.minimap.enabled": false,
  "editor.formatOnSave": true,
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,
  "workbench.startupEditor": "none",
  "workbench.editor.enablePreview": false,
  "terminal.integrated.defaultProfile.linux": "zsh",
  "git.autofetch": true,
  "git.confirmSync": false,
  "extensions.ignoreRecommendations": false,
  "settingsSync.ignoredSettings": [
    "terminal.integrated.cwd",
    "python.defaultInterpreterPath"
  ],
  "settingsSync.ignoredExtensions": []
}
```

### Web · TS Profile

Purpose: React, Next.js, TypeScript, Tailwind, and day-to-day FastAPI full-stack work.

Recommended extensions:

- `dbaeumer.vscode-eslint` — ESLint
- `esbenp.prettier-vscode` — Prettier
- `bradlc.vscode-tailwindcss` — Tailwind CSS IntelliSense
- `dsznajder.es7-react-js-snippets` — ES7 React snippets
- `formulahendry.auto-rename-tag` — Auto Rename Tag
- `humao.rest-client` — REST Client
- `ms-python.python` — Python
- `ms-python.vscode-pylance` — Pylance
- `charliermarsh.ruff` — Ruff
- `ms-vscode.js-debug` — JavaScript debugger

Profile settings:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.tabSize": 2,
  "editor.fontSize": 14,
  "workbench.colorTheme": "One Dark Pro",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  },
  "python.analysis.typeCheckingMode": "basic"
}
```

Use this Profile for this repository during normal full-stack work. Switch to Systems only when focusing on Rust crates under `backend/libs/`.

### Systems Profile

Purpose: Go, Rust, C/C++, Protobuf, and native debugging.

Recommended extensions:

- `golang.go` — Go
- `rust-lang.rust-analyzer` — rust-analyzer
- `llvm-vs-code-extensions.vscode-clangd` — clangd
- `ms-vscode.cpptools` — C/C++
- `vadimcn.vscode-lldb` — CodeLLDB
- `tamasfe.even-better-toml` — TOML
- `zxh404.vscode-proto3` — Proto3
- `ms-azuretools.vscode-docker` — Docker, optional if not inherited
- `ms-vscode-remote.remote-ssh` — Remote SSH, optional if not inherited

Profile settings:

```json
{
  "editor.formatOnSave": true,
  "editor.tabSize": 4,
  "editor.fontSize": 14,
  "workbench.colorTheme": "Monokai Pro",
  "[rust]": {
    "editor.defaultFormatter": "rust-lang.rust-analyzer"
  },
  "[go]": {
    "editor.defaultFormatter": "golang.go",
    "editor.insertSpaces": false,
    "editor.tabSize": 4
  },
  "[cpp]": {
    "editor.defaultFormatter": "llvm-vs-code-extensions.vscode-clangd"
  },
  "[c]": {
    "editor.defaultFormatter": "llvm-vs-code-extensions.vscode-clangd"
  }
}
```

### AI · ML Profile

Purpose: Python, Jupyter, PyTorch, data exploration, and LLM experimentation.

Recommended extensions:

- `ms-python.python` — Python
- `ms-python.vscode-pylance` — Pylance
- `charliermarsh.ruff` — Ruff
- `ms-toolsai.jupyter` — Jupyter
- `ms-toolsai.vscode-jupyter-cell-tags` — Jupyter Cell Tags
- `ms-toolsai.vscode-jupyter-slideshow` — Jupyter Slide Show
- `ms-toolsai.datawrangler` — Data Wrangler
- `ms-python.debugpy` — Python Debugger
- `mechatroner.rainbow-csv` — Rainbow CSV
- `continue.continue` — Continue, if preferred for local LLM workflows

Profile settings:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "charliermarsh.ruff",
  "editor.tabSize": 4,
  "editor.rulers": [88],
  "workbench.colorTheme": "GitHub Dark",
  "python.analysis.typeCheckingMode": "basic",
  "jupyter.notebookFileRoot": "${workspaceFolder}",
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".ipynb_checkpoints": true
  }
}
```

## Setup Steps

1. Sign in to VS Code with a GitHub or Microsoft account.
2. Run `Settings Sync: Turn On...` from the Command Palette.
3. Select the sync categories listed in **Sync Scope**.
4. Run `Profiles: Create Profile...` and create:
   - `Web · TS`
   - `Systems`
   - `AI · ML`
5. Switch into each Profile and install only the extensions listed for that Profile.
6. Apply the Profile-specific `settings.json` values.
7. Run `Profiles: Export Profile...` for each Profile and keep a local backup outside the project repository.
8. Open this repository with `Web · TS` for normal work. Switch to `Systems` for focused Rust work.

## Repository Workspace Guidance

For this repository, keep project-specific VS Code files under `.vscode/` only when they encode shared project behavior:

- `.vscode/settings.json` — committed project formatting and test defaults.
- `.vscode/extensions.json` — committed team extension recommendations.
- `.vscode/launch.json` — committed shared debug targets.
- `.vscode/tasks.json` — committed shared build/test commands.

Do not commit personal files:

- `.vscode/*.code-snippets`
- `.vscode/settings.local.json`
- `.history/`

## Validation

Manual validation after setup:

1. Reload VS Code in the Default Profile and confirm only shared extensions are active.
2. Switch to `Web · TS` and confirm TypeScript, Tailwind, ESLint, Prettier, Python, Pylance, and Ruff are available.
3. Switch to `Systems` and confirm `rust-analyzer`, `clangd`, Go, and LLDB are available.
4. Switch to `AI · ML` and confirm Python, Ruff, Pylance, Jupyter, and Data Wrangler are available.
5. Sign in on a second machine or VS Code Insiders profile and confirm Profiles sync.

## Risks

- **Extension ID drift:** Marketplace extension IDs can change if an extension is renamed or deprecated. Verify IDs in the Extensions view before installing in a new environment.
- **Settings conflict:** Workspace settings override Profile settings. If formatting differs in a project, inspect `.vscode/settings.json` first.
- **Heavy extension leakage:** Installing `rust-analyzer`, `clangd`, or Jupyter into the Default Profile defeats isolation. Keep heavyweight tools in their dedicated Profiles.
- **Secret exposure:** Do not place tokens, API keys, or machine-local interpreter paths in synced user settings.
