# Worktree Merge Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge evaluated worktree changes into `dev` branch across 5 PRs, ordered by risk (lowest first).

**Architecture:** Each worktree is a full project snapshot without git history. Unique changes are extracted per-PR via file copy from `worktrees/<id>/` into a feature branch. Common baseline changes (shared across all worktrees: config, deploy/ansible, model-server, docs, benchmark) are included only in the first PR; subsequent PRs copy only their unique files.

**Tech Stack:** Python (pytest, ruff), Rust (cargo test), TypeScript (vitest, ESLint), Ansible

**Worktree inventory:**

| PR | Source | Unique files | Score |
|----|--------|-------------|-------|
| 1 | UHLC0N_raven | 2 Rust files | 10/10 |
| 2 | UHLC0N_prism | 5 Python files (agents/) | 8/10 |
| 3 | TGRB7U composite | prism base + quartz guard + sigma tests | 8/10 |
| 4a | UHLC0N_quartz (auth) | ~12 security files | 8/10 |
| 4b | UHLC0N_quartz (config) | ~8 config rename files | 8/10 |

**Not merging:** UHLC0N_sigma (5/10, incomplete), TGRB7U_raven (5/10, missing chunk guard), 342ETV/3Y9LZF x6 (7/10, already merged as d89f0620).

---

## PR 1: UHLC0N_raven — Rust async P0 fix

**Branch:** `fix/net-io-mineru-async-blocking`
**Source:** `worktrees/UHLC0N_raven/`
**Risk:** Very Low — 2 files, surgical fix, no Python changes

### Task 1: Create branch

**Step 1: Ensure clean working tree**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
git stash --include-untracked
```

**Step 2: Create branch from dev**

```bash
git checkout dev
git pull origin dev
git checkout -b fix/net-io-mineru-async-blocking
```

### Task 2: Copy the 2 unique Rust files

**Files:**
- Modify: `backend/libs/net-io/Cargo.toml`
- Modify: `backend/libs/net-io/src/mineru.rs`

**Step 1: Copy files from worktree**

```bash
cp worktrees/UHLC0N_raven/backend/libs/net-io/Cargo.toml backend/libs/net-io/Cargo.toml
cp worktrees/UHLC0N_raven/backend/libs/net-io/src/mineru.rs backend/libs/net-io/src/mineru.rs
```

**Step 2: Verify the diff is minimal and correct**

```bash
git diff backend/libs/net-io/
```

Expected: ~10 lines changed.
- `Cargo.toml`: tokio `fs` feature added
- `mineru.rs`: `std::fs::read` -> `tokio::fs::read`, serial loop -> `futures::future::join_all`

**Step 3: Verify no other files were accidentally changed**

```bash
git diff --stat
```

Expected: exactly 2 files changed.

### Task 3: Run Rust tests

**Step 1: Run cargo check**

```bash
cd backend/libs/net-io
cargo check
```

Expected: no errors

**Step 2: Run cargo test**

```bash
cargo test
```

Expected: all tests pass

**Step 3: Return to project root**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
```

### Task 4: Verify Python-side compatibility

**Step 1: Run ruff**

```bash
cd backend
uv run ruff check
```

Expected: no new errors (no Python files changed)

**Step 2: Return to project root**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
```

### Task 5: Commit

**Step 1: Stage and commit**

```bash
git add backend/libs/net-io/Cargo.toml backend/libs/net-io/src/mineru.rs
git commit -m "$(cat <<'EOF'
fix(net-io): replace std::fs::read with tokio::fs::read in MinerU upload

std::fs::read blocked the tokio worker thread during PDF uploads,
starving concurrent requests. tokio::fs::read uses spawn_blocking
internally. Also parallelizes independent upload futures via join_all.
EOF
)"
```

### Task 6: Create PR

```bash
git push -u origin fix/net-io-mineru-async-blocking
gh pr create --title "fix(net-io): replace blocking std::fs::read in MinerU upload" --body "$(cat <<'EOF'
## Summary
- Replace `std::fs::read` with `tokio::fs::read` in `upload_local_file` to avoid blocking the tokio worker thread
- Add tokio `fs` feature flag to `net-io/Cargo.toml`
- Parallelize independent upload futures via `futures::future::join_all`

## Test plan
- [x] `cargo check` passes
- [x] `cargo test` passes
- [x] No Python changes — ruff clean
EOF
)"
```

---

## PR 2: UHLC0N_prism — State Transition Guards

**Branch:** `feat/state-transition-guards`
**Source:** `worktrees/UHLC0N_prism/`
**Risk:** Low — additive guards, existing tests updated

### Task 7: Create branch

```bash
git checkout dev
git checkout -b feat/state-transition-guards
```

### Task 8: Copy the 5 unique files

**Files:**
- Modify: `backend/src/agents/contracts.py`
- Modify: `backend/src/agents/orchestrator.py`
- Modify: `backend/src/agents/state_persistence.py`
- Modify: `backend/tests/agents/test_state_persistence_layer.py`
- Create: `backend/tests/agents/test_state_transition_guard.py`

**Step 1: Copy modified files**

```bash
cp worktrees/UHLC0N_prism/backend/src/agents/contracts.py backend/src/agents/contracts.py
cp worktrees/UHLC0N_prism/backend/src/agents/orchestrator.py backend/src/agents/orchestrator.py
cp worktrees/UHLC0N_prism/backend/src/agents/state_persistence.py backend/src/agents/state_persistence.py
cp worktrees/UHLC0N_prism/backend/tests/agents/test_state_persistence_layer.py backend/tests/agents/test_state_persistence_layer.py
```

**Step 2: Copy new test file**

```bash
cp worktrees/UHLC0N_prism/backend/tests/agents/test_state_transition_guard.py backend/tests/agents/test_state_transition_guard.py
```

**Step 3: Verify diff**

```bash
git diff --stat
```

Expected: 4 modified + 1 new file, all under `backend/src/agents/` and `backend/tests/agents/`.

### Task 9: Run tests

**Step 1: Run targeted agent tests**

```bash
cd backend
uv run pytest tests/agents/ -v
```

Expected: all pass (including new `test_state_transition_guard.py`)

**Step 2: Run full backend test suite**

```bash
uv run pytest tests/ -v --timeout=60
```

Expected: no regressions

**Step 3: Run ruff**

```bash
uv run ruff check
```

Expected: clean

### Task 10: Commit

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
git add backend/src/agents/contracts.py backend/src/agents/orchestrator.py backend/src/agents/state_persistence.py backend/tests/agents/test_state_persistence_layer.py backend/tests/agents/test_state_transition_guard.py
git commit -m "$(cat <<'EOF'
feat(agents): add defensive state-transition validation

Prevents illegal pipeline/phase status transitions (e.g., COMPLETED ->
RUNNING) from being silently persisted. Transition tables in contracts.py,
enforcement in state_persistence.py, defense-in-depth logging in orchestrator.
EOF
)"
```

### Task 11: Create PR

```bash
git push -u origin feat/state-transition-guards
gh pr create --title "feat(agents): add state-transition guards" --body "$(cat <<'EOF'
## Summary
- Add `InvalidStateTransitionError` and transition tables in `contracts.py`
- Enforce guards in `state_persistence.py` save() and _transactional_upsert()
- Defense-in-depth logging in `orchestrator.py` at 3 mutation points
- New test file: `test_state_transition_guard.py`

## Test plan
- [x] `pytest tests/agents/ -v` passes
- [x] Full backend test suite — no regressions
- [x] `ruff check` clean
EOF
)"
```

---

## PR 3: TGRB7U Composite — Chat SSE Abort + Debounce + A11y

**Branch:** `feat/chat-sse-abort-debounce`
**Source:** prism (base) + quartz (chunk guard) + sigma (model-server tests)
**Risk:** Medium — frontend behavior change, multi-source merge

### Task 12: Create branch

```bash
git checkout dev
git checkout -b feat/chat-sse-abort-debounce
```

### Task 13: Copy prism base files (3 frontend source + vitest config)

**Files from `worktrees/TGRB7U_prism_quick/`:**
- Modify: `frontend/src/features/chat/providers/acmgChatProvider.ts`
- Modify: `frontend/src/features/chat/components/ChatActionBubble.tsx`
- Modify: `frontend/src/features/chat/components/ChatView.tsx`
- Modify: `frontend/vitest.config.ts`

```bash
cp worktrees/TGRB7U_prism_quick/frontend/src/features/chat/providers/acmgChatProvider.ts frontend/src/features/chat/providers/acmgChatProvider.ts
cp worktrees/TGRB7U_prism_quick/frontend/src/features/chat/components/ChatActionBubble.tsx frontend/src/features/chat/components/ChatActionBubble.tsx
cp worktrees/TGRB7U_prism_quick/frontend/src/features/chat/components/ChatView.tsx frontend/src/features/chat/components/ChatView.tsx
cp worktrees/TGRB7U_prism_quick/frontend/vitest.config.ts frontend/vitest.config.ts
```

### Task 14: Copy prism test files (3 new)

**Files from `worktrees/TGRB7U_prism_quick/`:**
- Create: `frontend/tests/features/chat/ChatActionBubble.test.tsx`
- Create: `frontend/tests/features/chat/acmgChatProvider.test.tsx`
- Create: `frontend/tests/features/chat/useChatSessions.test.tsx`

```bash
mkdir -p frontend/tests/features/chat
cp worktrees/TGRB7U_prism_quick/frontend/tests/features/chat/ChatActionBubble.test.tsx frontend/tests/features/chat/
cp worktrees/TGRB7U_prism_quick/frontend/tests/features/chat/acmgChatProvider.test.tsx frontend/tests/features/chat/
cp worktrees/TGRB7U_prism_quick/frontend/tests/features/chat/useChatSessions.test.tsx frontend/tests/features/chat/
```

### Task 15: Cherry-pick quartz chunk-discard guard

**File:** `frontend/src/features/chat/providers/acmgChatProvider.ts`

This is the critical safety improvement: after `abortStream()` is called, the `streamAborted` flag causes `transformMessage()` to drop subsequent SSE chunks, preventing stale tokens from leaking into a session the user has navigated away from.

**Step 1: View quartz's chunk guard implementation**

```bash
diff worktrees/TGRB7U_prism_quick/frontend/src/features/chat/providers/acmgChatProvider.ts worktrees/TGRB7U_quartz_quick/frontend/src/features/chat/providers/acmgChatProvider.ts
```

**Step 2: Apply the chunk-discard guard to the current file**

The quartz version adds:
1. A `private streamAborted = false` instance field
2. Reset `this.streamAborted = false` at the start of each new request
3. Set `this.streamAborted = true` in the abort method
4. Early return in `transformMessage()`: `if (this.streamAborted) return originMessage`

Read the current file and the quartz file, then manually merge the chunk guard into the prism base. The prism base uses closure variables and `AbortSignal.any()` — keep those, just add the `streamAborted` flag and the `transformMessage` guard from quartz.

**Step 3: Verify the merge**

```bash
grep -n "streamAborted\|transformMessage" frontend/src/features/chat/providers/acmgChatProvider.ts
```

Expected: both `streamAborted` flag references AND prism's `AbortSignal.any()` pattern present.

### Task 16: Copy sigma model-server test updates

**Files from `worktrees/TGRB7U_sigma_quick/`:**
- Modify: `services/model-server/tests/test_main_wiring.py`
- Modify: `services/model-server/tests/test_model_server_config.py`
- Modify: `services/model-server/tests/conftest.py`

```bash
cp worktrees/TGRB7U_sigma_quick/services/model-server/tests/test_main_wiring.py services/model-server/tests/test_main_wiring.py
cp worktrees/TGRB7U_sigma_quick/services/model-server/tests/test_model_server_config.py services/model-server/tests/test_model_server_config.py
cp worktrees/TGRB7U_sigma_quick/services/model-server/tests/conftest.py services/model-server/tests/conftest.py
```

### Task 17: Verify the composite

**Step 1: Check all changes**

```bash
git diff --stat
```

Expected:
- 3 frontend source files modified (ChatActionBubble, ChatView, acmgChatProvider)
- 1 vitest config modified
- 3 frontend test files new
- 3 model-server test files modified

**Step 2: Verify key features are present**

```bash
# Prism features: aria-busy, data-testid, AbortSignal.any()
grep "aria-busy" frontend/src/features/chat/components/ChatActionBubble.tsx
grep "data-testid" frontend/src/features/chat/components/ChatActionBubble.tsx

# Quartz feature: chunk-discard guard
grep "streamAborted" frontend/src/features/chat/providers/acmgChatProvider.ts
```

All three greps should return matches.

### Task 18: Run frontend tests

```bash
cd frontend
npm run type-check
npx vitest run
```

Expected: type-check passes, all vitest tests pass.

### Task 19: Run model-server tests

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/services/model-server
uv run pytest tests/test_main_wiring.py tests/test_model_server_config.py -v
```

Expected: all pass.

### Task 20: Run backend ruff (no Python source changes, but verify)

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/backend
uv run ruff check
```

### Task 21: Commit

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
git add frontend/src/features/chat/providers/acmgChatProvider.ts frontend/src/features/chat/components/ChatActionBubble.tsx frontend/src/features/chat/components/ChatView.tsx frontend/vitest.config.ts frontend/tests/features/chat/ChatActionBubble.test.tsx frontend/tests/features/chat/acmgChatProvider.test.tsx frontend/tests/features/chat/useChatSessions.test.tsx services/model-server/tests/test_main_wiring.py services/model-server/tests/test_model_server_config.py services/model-server/tests/conftest.py
git commit -m "$(cat <<'EOF'
feat(chat): add SSE abort mechanism, debounce guard, and a11y improvements

- SSE abort with chunk-discard guard: streamAborted flag drops stale
  chunks after abort, preventing token leakage into navigated-away sessions
- AbortSignal.any() for clean signal composition with SDK signal
- ChatActionBubble: ref-based double-click guard, aria-busy for screen
  readers, data-testid for stable selectors, keyboard a11y (Enter/Space)
- ChatView: abort on session switch and component unmount
- Vitest tests: ChatActionBubble (15 cases), acmgChatProvider (14 cases),
  useChatSessions
- Model-server test alignment: VLM rename updates
EOF
)"
```

### Task 22: Create PR

```bash
git push -u origin feat/chat-sse-abort-debounce
gh pr create --title "feat(chat): SSE abort + chunk guard + debounce + a11y" --body "$(cat <<'EOF'
## Summary
- SSE abort with `streamAborted` chunk-discard guard (from quartz) prevents stale token leakage after abort
- `AbortSignal.any()` signal composition (from prism) for clean SDK signal chaining
- ChatActionBubble: `aria-busy`, `data-testid`, ref-based double-click guard, keyboard a11y (from prism)
- ChatView: abort on session switch and unmount (from prism)
- 3 vitest test files with 30+ test cases
- Model-server test alignment (from sigma)

## Test plan
- [x] `npm run type-check` passes
- [x] `npx vitest run` passes
- [x] Model-server tests pass
- [x] `ruff check` clean
EOF
)"
```

---

## PR 4a: UHLC0N_quartz — Auth + Security Headers

**Branch:** `feat/security-auth-headers`
**Source:** `worktrees/UHLC0N_quartz/`
**Risk:** Medium — adds auth to API endpoints, new middleware

### Task 23: Create branch

```bash
git checkout dev
git checkout -b feat/security-auth-headers
```

### Task 24: Copy auth/security files (PR 1 of 2)

**Files from `worktrees/UHLC0N_quartz/`:**

Backend source:
- Modify: `backend/app/main.py` — SecurityHeadersMiddleware registration
- Create: `backend/src/utils/security_headers.py` — middleware implementation
- Modify: `backend/src/api/v1/chat.py` — `require_api_key` on 2 read endpoints
- Modify: `backend/src/api/v1/evidence.py` — `require_api_key` on 4 read endpoints
- Modify: `backend/src/api/v1/delta_audit.py` — `require_api_key`
- Modify: `backend/src/api/v1/source_link.py` — `require_api_key` on 2 endpoints
- Modify: `backend/pyproject.toml` — remove unversioned `socks>=0`

Backend tests:
- Create: `backend/tests/api/test_auth.py`
- Create: `backend/tests/api/test_pipeline_auth.py`

Deploy (non-breaking):
- Modify: `deploy/ansible/roles/nginx/templates/lingua-seeker.conf.j2` — HSTS/security headers
- Modify: `deploy/ansible/roles/backend/templates/acmg-backend.service.j2` — `forwarded-allow-ips` restricted

```bash
cp worktrees/UHLC0N_quartz/backend/app/main.py backend/app/main.py
cp worktrees/UHLC0N_quartz/backend/src/utils/security_headers.py backend/src/utils/security_headers.py
cp worktrees/UHLC0N_quartz/backend/src/api/v1/chat.py backend/src/api/v1/chat.py
cp worktrees/UHLC0N_quartz/backend/src/api/v1/evidence.py backend/src/api/v1/evidence.py
cp worktrees/UHLC0N_quartz/backend/src/api/v1/delta_audit.py backend/src/api/v1/delta_audit.py
cp worktrees/UHLC0N_quartz/backend/src/api/v1/source_link.py backend/src/api/v1/source_link.py
cp worktrees/UHLC0N_quartz/backend/pyproject.toml backend/pyproject.toml
cp worktrees/UHLC0N_quartz/backend/tests/api/test_auth.py backend/tests/api/test_auth.py
cp worktrees/UHLC0N_quartz/backend/tests/api/test_pipeline_auth.py backend/tests/api/test_pipeline_auth.py
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/nginx/templates/lingua-seeker.conf.j2 deploy/ansible/roles/nginx/templates/lingua-seeker.conf.j2
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/backend/templates/acmg-backend.service.j2 deploy/ansible/roles/backend/templates/acmg-backend.service.j2
```

### Task 25: Verify diff scope

```bash
git diff --stat
```

Expected: ~11 files, NO config rename changes, NO frontend auth changes, NO docker-compose changes. If any of those appear, revert them — they belong in PR 4b.

### Task 26: Run tests

```bash
cd backend
uv run ruff check
uv run pytest tests/api/test_auth.py tests/api/test_pipeline_auth.py -v
uv run pytest tests/ -v --timeout=60
```

Expected: ruff clean, auth tests pass, no regressions.

### Task 27: Commit

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
git add -A
git commit -m "$(cat <<'EOF'
feat(security): add API key auth to read endpoints and security headers

- SecurityHeadersMiddleware with HSTS variant for production
- require_api_key dependency on chat/evidence/delta_audit/source_link read endpoints
- Remove unversioned socks>=0 dependency (supply-chain risk)
- Nginx HSTS/security headers, forwarded-allow-ips restricted to 127.0.0.1
- Auth tests: test_auth.py, test_pipeline_auth.py
EOF
)"
```

### Task 28: Create PR

```bash
git push -u origin feat/security-auth-headers
gh pr create --title "feat(security): API key auth + security headers" --body "$(cat <<'EOF'
## Summary
- SecurityHeadersMiddleware (CSP, X-Content-Type-Options, etc.) with HSTS subclass for production
- `require_api_key` on all read-only API endpoints (chat, evidence, delta_audit, source_link)
- Remove unversioned `socks>=0` dependency
- Nginx security headers, `forwarded-allow-ips` restricted

## Test plan
- [x] `ruff check` clean
- [x] Auth tests pass
- [x] Full backend test suite — no regressions

## Note
Config rename (mineru_local_*) is in a separate follow-up PR.
EOF
)"
```

---

## PR 4b: UHLC0N_quartz — Config Rename + Deployment Hardening

**Branch:** `chore/config-rename-deploy-hardening`
**Source:** `worktrees/UHLC0N_quartz/`
**Risk:** Medium-High — breaking config changes, needs coordinated deployment

**Prerequisite:** PR 4a must be merged first.

### Task 29: Create branch

```bash
git checkout dev
git checkout -b chore/config-rename-deploy-hardening
```

### Task 30: Copy remaining config/deploy files (PR 2 of 2)

**Files from `worktrees/UHLC0N_quartz/`:**

Config changes (BREAKING — coordinate with deployment):
- Modify: `backend/src/core/config.py` — mineru config field renames
- Modify: `backend/config/defaults/main.yaml`
- Modify: `backend/config/environments/development.yaml`
- Modify: `backend/config/templates/config.yaml.j2`

Deploy hardening:
- Modify: `deploy/ansible/roles/backend/templates/production.yaml.j2`
- Modify: `deploy/ansible/roles/frontend/tasks/main.yml`
- Create: `deploy/ansible/roles/frontend/templates/frontend.env.j2` — restricted-permission env file
- Modify: `deploy/ansible/roles/frontend/templates/acmg-frontend.service.j2`
- Modify: `deploy/ansible/roles/model-server/tasks/main.yml`
- Modify: `deploy/ansible/roles/model-server/templates/acmg-model-server.service.j2`
- Modify: `deploy/ansible/inventories/production/group_vars/all.yml`
- Modify: `deploy/ansible/inventories/production/hosts-single-server.yml.example`

Frontend auth:
- Modify: `frontend/middleware.ts`
- Modify: `frontend/next.config.ts`
- Modify: `frontend/src/features/auth/hooks/useAuth.ts`
- Modify: `frontend/src/features/auth/services/auth.ts`
- Create: `frontend/app/api/auth/login/route.ts`
- Create: `frontend/app/api/auth/logout/` (directory)

Other:
- Modify: `docker-compose.yml`
- Modify: `services/model-server/app/config.py`
- Modify: `services/model-server/app/enums/model_type.py`
- Modify: `services/model-server/app/models/__init__.py`
- Modify: `services/model-server/app/models/schemas.py`
- Modify: `services/model-server/main.py`
- Modify: `services/model-server/pyproject.toml`
- Modify: `services/model-server/tests/conftest.py`
- Modify: `services/model-server/tests/test_main_wiring.py`
- Modify: `services/model-server/tests/test_model_server_config.py`
- Modify: `services/model-server/app/api/embedding.py`
- Modify: `services/model-server/app/api/rerank.py`

```bash
# Config
cp worktrees/UHLC0N_quartz/backend/src/core/config.py backend/src/core/config.py
cp worktrees/UHLC0N_quartz/backend/config/defaults/main.yaml backend/config/defaults/main.yaml
cp worktrees/UHLC0N_quartz/backend/config/environments/development.yaml backend/config/environments/development.yaml
cp worktrees/UHLC0N_quartz/backend/config/templates/config.yaml.j2 backend/config/templates/config.yaml.j2

# Deploy
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/backend/templates/production.yaml.j2 deploy/ansible/roles/backend/templates/production.yaml.j2
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/frontend/tasks/main.yml deploy/ansible/roles/frontend/tasks/main.yml
mkdir -p deploy/ansible/roles/frontend/templates
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/frontend/templates/frontend.env.j2 deploy/ansible/roles/frontend/templates/
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/frontend/templates/acmg-frontend.service.j2 deploy/ansible/roles/frontend/templates/
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/model-server/tasks/main.yml deploy/ansible/roles/model-server/tasks/main.yml
cp worktrees/UHLC0N_quartz/deploy/ansible/roles/model-server/templates/acmg-model-server.service.j2 deploy/ansible/roles/model-server/templates/
cp worktrees/UHLC0N_quartz/deploy/ansible/inventories/production/group_vars/all.yml deploy/ansible/inventories/production/group_vars/all.yml
cp worktrees/UHLC0N_quartz/deploy/ansible/inventories/production/hosts-single-server.yml.example deploy/ansible/inventories/production/hosts-single-server.yml.example

# Frontend
cp worktrees/UHLC0N_quartz/frontend/middleware.ts frontend/middleware.ts
cp worktrees/UHLC0N_quartz/frontend/next.config.ts frontend/next.config.ts
cp worktrees/UHLC0N_quartz/frontend/src/features/auth/hooks/useAuth.ts frontend/src/features/auth/hooks/useAuth.ts
cp worktrees/UHLC0N_quartz/frontend/src/features/auth/services/auth.ts frontend/src/features/auth/services/auth.ts
mkdir -p frontend/app/api/auth/login
cp worktrees/UHLC0N_quartz/frontend/app/api/auth/login/route.ts frontend/app/api/auth/login/
cp -r worktrees/UHLC0N_quartz/frontend/app/api/auth/logout frontend/app/api/auth/

# Model server
cp worktrees/UHLC0N_quartz/services/model-server/app/config.py services/model-server/app/config.py
cp worktrees/UHLC0N_quartz/services/model-server/app/enums/model_type.py services/model-server/app/enums/model_type.py
cp worktrees/UHLC0N_quartz/services/model-server/app/models/__init__.py services/model-server/app/models/__init__.py
cp worktrees/UHLC0N_quartz/services/model-server/app/models/schemas.py services/model-server/app/models/schemas.py
cp worktrees/UHLC0N_quartz/services/model-server/main.py services/model-server/main.py
cp worktrees/UHLC0N_quartz/services/model-server/pyproject.toml services/model-server/pyproject.toml
cp worktrees/UHLC0N_quartz/services/model-server/tests/conftest.py services/model-server/tests/conftest.py
cp worktrees/UHLC0N_quartz/services/model-server/tests/test_main_wiring.py services/model-server/tests/test_main_wiring.py
cp worktrees/UHLC0N_quartz/services/model-server/tests/test_model_server_config.py services/model-server/tests/test_model_server_config.py
cp worktrees/UHLC0N_quartz/services/model-server/app/api/embedding.py services/model-server/app/api/embedding.py
cp worktrees/UHLC0N_quartz/services/model-server/app/api/rerank.py services/model-server/app/api/rerank.py

# Docker
cp worktrees/UHLC0N_quartz/docker-compose.yml docker-compose.yml
```

### Task 31: Verify diff

```bash
git diff --stat
```

Expected: ~30 files. Verify NO overlap with PR 4a files (main.py, security_headers.py, API route files). If overlap detected, revert those specific files.

### Task 32: Run tests

```bash
cd backend
uv run ruff check
uv run pytest tests/ -v --timeout=60

cd /data/yangzs/Projects/01_ACMG_Lingua/services/model-server
uv run pytest tests/ -v

cd /data/yangzs/Projects/01_ACMG_Lingua/frontend
npm run type-check
```

### Task 33: Commit

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua
git add -A
git commit -m "$(cat <<'EOF'
chore(config): rename mineru_local config fields + deployment hardening

BREAKING CHANGE: mineru_local_api_url -> mineru_local_model_server_url,
mineru_local_backend removed, added mineru_local_model_id and mineru_local_dpi.

- Frontend env secrets moved to restricted-permission EnvironmentFile (0600)
- Frontend auth flow updates (login/logout routes, middleware)
- Model-server config simplification
- Docker-compose updates
EOF
)"
```

### Task 34: Create PR

```bash
git push -u origin chore/config-rename-deploy-hardening
gh pr create --title "chore(config): mineru config rename + deploy hardening" --body "$(cat <<'EOF'
## Summary
- **BREAKING**: `mineru_local_api_url` -> `mineru_local_model_server_url`, `mineru_local_backend` removed, added `mineru_local_model_id` + `mineru_local_dpi`
- Frontend secrets moved to `EnvironmentFile` with 0600 permissions (not visible via `systemctl show`)
- Frontend auth flow: login/logout API routes, middleware updates
- Model-server config simplification

## Deployment coordination required
- Config rename must be deployed atomically with backend + model-server restart
- Frontend env file requires Ansible role update

## Test plan
- [x] `ruff check` clean
- [x] Backend tests pass
- [x] Model-server tests pass
- [x] Frontend type-check passes
EOF
)"
```

---

## Post-Merge Checklist

### Task 35: After all PRs merged

1. **Delete feature branches**

```bash
git branch -d fix/net-io-mineru-async-blocking
git branch -d feat/state-transition-guards
git branch -d feat/chat-sse-abort-debounce
git branch -d feat/security-auth-headers
git branch -d chore/config-rename-deploy-hardening
```

2. **Update progress.txt**

```
[2026-06-17] [Merge UHLC0N_raven: Rust async P0 fix] [done]
[2026-06-17] [Merge UHLC0N_prism: state transition guards] [done]
[2026-06-17] [Merge TGRB7U composite: chat SSE abort + debounce + a11y] [done]
[2026-06-17] [Merge UHLC0N_quartz: security auth + headers] [done]
[2026-06-17] [Merge UHLC0N_quartz: config rename + deploy hardening] [done]
```

3. **Clean up worktree archives** (optional — after confirming all merges successful)

```bash
# Only after all PRs are merged and verified in production
rm -rf worktrees/UHLC0N_raven worktrees/UHLC0N_prism worktrees/TGRB7U_prism_quick worktrees/TGRB7U_quartz_quick worktrees/TGRB7U_sigma_quick worktrees/UHLC0N_quartz
```
