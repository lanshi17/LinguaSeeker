# AGENTS.md

Project specification — all developers and AI Agents must follow these rules.

---

## 1. Hard Rules

### 1.1 Dependency Management

Modern tools only. System-level installs are prohibited.

| Language | Tool | Prohibited |
|---|---|---|
| Python | `uv` | `pip` / `pip3` / system Python |
| Node.js | `nvm` + `npm` | system global Node |
| Rust | `cargo` | — |
| C/C++ | `cmake` | — |

- All dependencies must be declared in config files (`pyproject.toml` / `package.json` / `Cargo.toml`).
- Production dependencies must be locked (`uv.lock` / `package-lock.json` / `Cargo.lock`).

### 1.2 Directory Structure

| Purpose | Path |
|---|---|
| Backend entry | `app/main.py`, business logic in `src/` and subdirectories |
| Frontend entry | Next.js App Router in `frontend/app/`, components in `frontend/components/` |
| Documentation | `docs/` (archive: `docs/archive/`) |
| Tests | `tests/` (Rust: `libs/rust-io/tests/`) |
| Scripts | `scripts/` |
| Database | `database/` (migrations: `migrations/`, seeds: `seeds/`) |
| Deployment | `deploy/` |
| Logs | `logs/` (timestamped, e.g. `2026-05-04_143000.log`) |


### 1.2.1 Architecture Preference: Orchestrated Vertical Slice

New modules should prefer **Orchestrated Vertical Slice Architecture**:

- `src/agents/` is the orchestrator: LangGraph topology, global Pydantic state, router decisions, node telemetry.
- `src/core/<feature>/` contains vertical feature slices. A non-trivial slice should expose an `api.py` node adapter, keep pure domain behavior in `core.py`, wrap LLM/DB/Rust/external dependencies in `providers.py`, and define feature-local contracts in `contracts.py` or `schema.py`.
- `src/utils/`, `src/dao/`, Rust crates, and shared clients are infrastructure. Business core code must not depend directly on SDK clients when a provider boundary is practical.
- Workflow code wires nodes and edges only; feature packages own the biomedical, translation, standardization, feedback, and report-generation decisions.
- Cross-node state uses typed Pydantic/dataclass/TypedDict contracts. Do not introduce stable bare-dict return contracts.

### 1.3 Branching & Commits

- Main branch: **`dev`**. `master` is merge-only, no direct pushes.
- Follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`, English descriptions.

### 1.4 Code Standards

- Python: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html), enforced by Ruff.
- TypeScript: [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html), enforced by ESLint.

### 1.5 Security

- Secrets (passwords, API keys, tokens) must be injected via env vars or `.env`. **No hardcoding.**
- `.env` must be excluded in `.gitignore`.

### 1.6 Logging & Testing

- Logging: `loguru`, output to `logs/`.
- Testing: Backend uses `pytest`, Frontend uses its respective framework.

---

## 2. Backend Development

### 2.1 Use `uv` for All Python Operations

**Prohibited**: `pip install`, `python main.py`, system-level installs. All operations go through `uv`:

```bash
# Dependency management
uv add <package>              # production dependency
uv add --dev <package>        # dev dependency
uv pip install -e ".[dev]"    # install project + dependencies
uv lock                       # update lock file

# Execution
uv run python path/to/script.py
uv run python -m app.main
uv run uvicorn app.main:app --reload
uv run ruff check
uv run pytest
uv run pytest tests/path/to/test_file.py::test_function_name
```

### 2.2 Reuse Old Version Code

The old codebase lives in **`.old_version/`**. Always check it before writing new code.

| Directory | Contents |
|---|---|
| `.old_version/src/` | Core business logic (agents, api, domain, infrastructure, services, tools, utils) |
| `.old_version/utils/` | Shared utility modules |
| `.old_version/configs/` | App and database configuration |
| `.old_version/scripts/` | Ops scripts (log cleanup, cache purge, data sync, etc.) |
| `.old_version/database/` | Alembic migrations, Neo4j, Qdrant, MinIO configs |
| `.old_version/tests/` | Existing test cases |
| `.old_version/knowledge_docs/` | Knowledge base documents |
| `.old_version/lesson.md` | Past retrospective notes |
| `.old_version/prd.json` | Product requirements |

**Workflow**: Search first → reuse preferentially → adapt to new architecture → annotate source for complex migrations.

```bash
grep -r "keyword" .old_version/src/
find .old_version/ -name "*.py" | xargs grep "ClassNameOrFunction"
tree .old_version/src/ -L 2
```

**Prohibited**: Writing new features without checking `.old_version/`, copying without adaptation, deleting `.old_version/`.

---

## 3. Workflow

### 3.1 Task Tracking

- Log each completed milestone in `progress.txt`: `[date] [task] [status]`.
- Every debugging iteration must be retrospected in `lesson.md` (problem, process, root cause, fix, prevention).

### 3.2 Worktree Isolation

- Light tasks: implement in current workspace.
- Medium/large tasks: create a Git Worktree, merge and delete branch on completion.

### 3.3 Code Review

- All changes require Code Review before merge.
- AI-generated code must be reviewed and approved by a human.

### 3.4 Requirement Clarification

- Ambiguous requirements must be clarified before implementation. **No assumptions.**

---

## 4. Behavioral Guidelines

### 4.1 Think Before Coding

**No assumptions. No hidden confusion. Surface tradeoffs.**

- State assumptions explicitly. Ask when unsure.
- Present all interpretations, never silently pick one.
- Propose simpler alternatives when they exist. Push back when warranted.
- If something is unclear, stop. Explain what's confusing, then ask.

### 4.2 Simplicity First

**Minimal code solves the problem. No speculative design.**

- Don't add features beyond the requirement.
- Don't create abstractions for one-off code.
- Don't add flexibility or configurability that wasn't requested.
- Don't add error handling for impossible scenarios.
- If 200 lines can be 50, rewrite.

### 4.3 Precise Changes

**Only touch what's necessary. Only clean up what you introduced.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor parts that aren't broken. Match existing style.
- If you find unrelated dead code, mention it — don't delete it.
- Standard: every line of diff should trace back to the user's request.

### 4.4 Goal-Driven Execution

**Define success criteria. Loop until verified.**

Convert tasks into verifiable goals:
- "Add validation" → write tests for invalid input, then make them pass.
- "Fix bug" → write a reproduction test, then make it pass.
- "Refactor X" → ensure tests pass before and after.

Multi-step tasks need a brief plan:
```
1. [Step] → Verify: [Check]
2. [Step] → Verify: [Check]
```

---

## 5. Violations

- Code that violates these rules must not be merged into the main branch.
- AI Agent violations must be recorded in `lesson.md` and corrected.
