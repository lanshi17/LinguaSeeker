# Chat-First ACMG System - Implementation Plan

## TL;DR
> **Summary**: Build a complete chat-first frontend for ACMG-PS3 evidence analysis with real-time WebSocket updates, file upload, clarification interactions, and evidence results display.
> **Deliverables**: 9 source files, vite.config.ts, types, router, store, API client, WebSocket hook, 6+ components
> **Effort**: Large (greenfield build, 50+ TODOs)
> **Parallel**: YES - Wave 1 (foundation) → Wave 2-4 (components in parallel) → Wave 5 (integration)
> **Critical Path**: vite.config.ts → types → store → useChatWebSocket → ChatInterface → sub-components

## Context
### Original Request
Build a chat-first single-page application for an ACMG-PS3 evidence intelligence system. The /chat route is the primary interaction entry point with a 70/30 split layout (message flow + collapsible context panel). Features include WebSocket real-time updates, file upload with drag-drop, clarification interactions with countdown timers, evidence result cards, and full TypeScript type safety.

### Interview Summary
- **UI Framework**: Ant Design 6.0+ (to be installed)
- **HTTP Client**: Axios (to be installed) — user explicitly confirmed
- **WebSocket**: Native WebSocket (NOT socket.io) with heartbeat/reconnect
- **API Endpoints**: Chat-specific endpoints (`/chat/*`) — user confirmed these are authoritative
- **Drag-Drop**: Use existing react-dnd (already installed)
- **Markdown**: react-markdown + DOMPurify (already installed)
- **State**: Zustand with immer middleware
- **Testing**: Vitest (already configured)

### Metis Review (gaps addressed)
**CRITICAL FIXES APPLIED:**
1. **antd version**: Must use `antd@^6.0.0` for React 19 compatibility
2. **vite.config.ts**: Created as first task (doesn't exist in greenfield)
3. **WebSocket StrictMode**: Use `useRef` pattern for connection tracking (React 19 double-mount)
4. **Zustand middleware order**: `persist(immer((set) => ...))` — immer INSIDE persist
5. **Markdown security**: Use `react-markdown` + `rehype-sanitize` (primary), DOMPurify supplementary only

**SCOPE CREEP DEFERRED TO V2:**
- Input entity highlighting (gene/variant/disease NER) — requires backend NLP service
- "为什么是PS3?" follow-up — no backend endpoint exists
- Streaming text animation for agent messages
- Dark mode / theme switching
- Comprehensive unit test coverage (ship working code first)

## Work Objectives
### Core Objective
Create a fully functional chat interface for ACMG evidence analysis with real-time WebSocket communication, file upload capabilities, clarification interactions, and evidence result display. The system must handle all message types (clarification, progress, result, system) and provide a responsive, accessible UI.

### Deliverables
1. `vite.config.ts` — Vite configuration with proxy and path aliases
2. `src/types/chat.ts` — Complete TypeScript definitions for chat domain
3. `src/types/api.ts` — API request/response types
4. `src/api/client.ts` — Axios client with interceptors
5. `src/store/chatStore.ts` — Zustand store with immer and persist
6. `src/hooks/useChatWebSocket.ts` — WebSocket hook with heartbeat/reconnect
7. `src/router/index.tsx` — React Router configuration with auth guard
8. `src/pages/ChatPage.tsx` — Main chat page component
9. `src/pages/ChatHistoryPage.tsx` — History page component
10. `src/components/chat/ChatInterface.tsx` — Main container (70/30 layout)
11. `src/components/chat/MessageBubble.tsx` — Message renderer (4 types)
12. `src/components/chat/ClarificationButtons.tsx` — Options with countdown
13. `src/components/chat/FileUploadZone.tsx` — Drag-drop file upload
14. `src/components/chat/ContextPanel.tsx` — Right panel (PDF viewer placeholder)
15. `src/components/chat/ProgressSteps.tsx` — Workflow progress display
16. `src/components/chat/ChatInput.tsx` — Input area with disclaimer
17. `src/App.tsx` — Root app component with Ant Design provider
18. `src/main.tsx` — Application entry point

### Definition of Done (verifiable conditions)
- [ ] All TypeScript compiles without errors (`npx tsc --noEmit` passes)
- [ ] ESLint passes (`npm run lint` passes)
- [ ] Build succeeds (`npm run build` creates dist/)
- [ ] Dev server starts and serves /chat route (`npm run dev` + curl 200)
- [ ] WebSocket connects and handles heartbeat (verified via browser dev tools)
- [ ] File upload accepts PDF via drag-drop (manual QA)
- [ ] Message history persists across page reloads (localStorage verification)
- [ ] Responsive layout works on mobile (< 768px hides context panel)

### Must Have
- Real-time WebSocket connection with auto-reconnect
- File upload via drag-drop (PDF, max 10MB)
- 4 message types: clarification, progress, result, system
- 120s countdown for clarification with red flash at 30s
- Mandatory disclaimer checkbox before submit
- Mobile responsive (hide context panel, full-screen results)
- Message history persistence (localStorage)
- Auth guard on /chat route
- ISO 8601 timestamps on all messages

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- ❌ Custom NLP entity recognition in input (not in spec, needs backend service)
- ❌ "为什么是PS3?" follow-up (no backend endpoint)
- ❌ Streaming text animation (not specified)
- ❌ Custom markdown parser (use react-markdown)
- ❌ Custom drag-drop (use react-dnd, already installed)
- ❌ Service worker / offline support (not in spec)
- ❌ Dark mode / theme switching (not in spec)
- ❌ Client-side routing transitions (not specified)
- ❌ i18n framework implementation (Constitution says "reserve interface")
- ❌ Comprehensive unit tests for every component (ship first, test incrementally)
- ❌ Using `marked` library for new code (use react-markdown)
- ❌ Using `any` type anywhere

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- **Test decision**: Tests-after (Vitest) + agent QA scenarios
- **QA policy**: Every task has agent-executed scenarios with specific commands
- **Evidence**: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

### Pre-Flight Checks (before ANY task)
```bash
# Verify no src/ exists (greenfield confirmation)
ls src/ 2>&1 | grep "No such file"
# Expected: Error message confirming src/ doesn't exist
```

### Foundation Verification (Wave 1)
```bash
# TypeScript compilation
npx tsc --noEmit
# Expected: Exit 0, zero errors

# Lint check
npm run lint
# Expected: Exit 0, no warnings treated as errors

# Build test
npm run build
# Expected: Exit 0, dist/index.html exists
```

### Component Verification (Wave 2-4)
```bash
# Dev server smoke test
npm run dev &
sleep 3
curl -s http://localhost:5173/chat | grep -q "ChatInterface\|chat-container"
# Expected: Match found (component renders)

# Route existence
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/chat/history
# Expected: 200
```

### WebSocket Verification (Wave 3)
```javascript
// In browser console after page load
const ws = new WebSocket('ws://localhost:8000/ws/chat/test-session');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
setInterval(() => ws.send(JSON.stringify({type: 'ping'})), 25000);
// Expected: Connection opens, ping/pong works
```

### Store Verification (Wave 2)
```javascript
// In browser console
const store = window.__ZUSTAND_STORE__ || useChatStore.getState();
store.sendMessage('Test message');
console.log(store.messages.length);
// Expected: 1 (message added)
```

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

#### Wave 1: Foundation (Sequential — all other waves depend on this)
- Task 1: Install dependencies (antd@^6.0.0, axios, immer)
- Task 2: Create vite.config.ts with proxy and path aliases
- Task 3: Create types (chat.ts, api.ts)
- Task 4: Create API client (src/api/client.ts)

#### Wave 2: State & Router (Parallel — depends on Wave 1)
- Task 5: Create Zustand store (chatStore.ts)
- Task 6: Create auth hook (useAuth.ts)
- Task 7: Create router configuration
- Task 8: Create App.tsx with Ant Design provider

#### Wave 3: WebSocket & Hooks (Parallel — depends on Wave 2)
- Task 9: Create useChatWebSocket hook
- Task 10: Create useFileUpload hook (react-dnd wrapper)
- Task 11: Create useScrollToBottom hook
- Task 12: Create useRelativeTime hook (timestamp formatting)

#### Wave 4: UI Components (Parallel — depends on Wave 2-3)
- Task 13: Create MessageBubble component
- Task 14: Create ClarificationButtons component
- Task 15: Create FileUploadZone component
- Task 16: Create ContextPanel component
- Task 17: Create ProgressSteps component
- Task 18: Create ChatInput component

#### Wave 5: Pages & Integration (Sequential — depends on Waves 2-4)
- Task 19: Create ChatInterface component (container)
- Task 20: Create ChatPage (main page)
- Task 21: Create ChatHistoryPage
- Task 22: Wire up main.tsx entry point

#### Wave 6: Final Verification (Parallel — all must pass)
- Task F1: TypeScript compilation audit
- Task F2: ESLint audit
- Task F3: Build verification
- Task F4: Manual QA checklist

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|------|------------|--------|
| 1 (deps) | - | 2, 3 |
| 2 (vite) | 1 | 3, 4 |
| 3 (types) | 1, 2 | 4, 5, 9 |
| 4 (api) | 2, 3 | 5, 9 |
| 5 (store) | 3, 4 | 6, 7, 9, 13-18 |
| 6 (auth) | 5 | 7, 19-21 |
| 7 (router) | 5, 6 | 19-21 |
| 8 (App) | 3 | 22 |
| 9 (ws) | 3, 4, 5 | 19 |
| 10 (file) | 3 | 18 |
| 11 (scroll) | - | 19 |
| 12 (time) | - | 13 |
| 13-18 (comps) | 3, 5 | 19 |
| 19 (container) | 5, 6, 7, 9, 11, 13-18 | 20, 21 |
| 20-21 (pages) | 19 | 22 |
| 22 (entry) | 8, 20, 21 | F1-F4 |
| F1-F4 | 22 | - |

### Agent Dispatch Summary (wave → task count → categories)
| Wave | Tasks | Categories | Skills |
|------|-------|------------|--------|
| 1 | 4 | foundation | npm, typescript |
| 2 | 4 | state, routing | typescript, react |
| 3 | 4 | hooks | react, websockets |
| 4 | 6 | components | react, ui |
| 5 | 4 | integration | react, typescript |
| 6 | 4 | verification | qa, testing |

## TODOs

### Wave 1: Foundation

- [x] 1. Install Dependencies

  **What to do**: Install antd@^6.0.0, axios, and immer. Pin exact versions to avoid breaking changes.
  **Must NOT do**: Install antd@5.x (React 19 incompatibility), skip --save-exact

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Simple dependency installation
  - Skills: `npm` — Verify installation success
  - Omitted: `typescript` — No code changes yet

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3 | Blocked By: -

  **References**:
  - Pattern: `package.json` — Check existing deps first
  - Docs: https://ant.design/docs/react/getting-started — Version 6.0+
  - Constraint: React 19.2.0 requires antd 6.0+

  **Acceptance Criteria**:
  - [ ] `npm install antd@^6.0.0 axios immer --save-exact` completes without errors
  - [ ] `package.json` contains exact versions
  - [ ] `node_modules/antd/package.json` shows version >= 6.0.0

  **QA Scenarios**:
  ```
  Scenario: Dependencies install correctly
    Tool: Bash
    Steps: npm install antd@^6.0.0 axios immer --save-exact
    Expected: Exit code 0, no peer dependency warnings
    Evidence: .sisyphus/evidence/task-1-deps-install.log

  Scenario: Verify antd version
    Tool: Bash
    Steps: cat node_modules/antd/package.json | grep '"version"' | head -1
    Expected: Contains "6." prefix
    Evidence: .sisyphus/evidence/task-1-antd-version.json
  ```

  **Commit**: YES | Message: `chore(deps): add antd@6, axios, immer for chat system` | Files: package.json, package-lock.json

---

- [x] 2. Create vite.config.ts

  **What to do**: Create Vite configuration with React plugin, dev server proxy for `/api/v1` to backend, and path alias `@` → `src/`.
  **Must NOT do**: Skip proxy configuration, use relative imports everywhere

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Foundation file, needs correctness
  - Skills: `typescript`, `vite` — Ensure proper config types
  - Omitted: `react` — No React code in config

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 4 | Blocked By: 1

  **References**:
  - Pattern: `tsconfig.node.json` references vite.config.ts
  - Docs: https://vitejs.dev/config/
  - Backend: Proxy `/api/v1` to `http://localhost:8000`

  **Acceptance Criteria**:
  - [ ] `vite.config.ts` exists at project root
  - [ ] Includes `@vitejs/plugin-react` import
  - [ ] Includes `resolve.alias: { '@': path.resolve(__dirname, 'src') }`
  - [ ] Includes `server.proxy: { '/api/v1': { target: 'http://localhost:8000', changeOrigin: true } }`
  - [ ] TypeScript compiles: `npx tsc --noEmit vite.config.ts`

  **QA Scenarios**:
  ```
  Scenario: Vite config exists and is valid
    Tool: Bash
    Steps: ls -la vite.config.ts && head -20 vite.config.ts
    Expected: File exists, contains React plugin import
    Evidence: .sisyphus/evidence/task-2-vite-config.txt

  Scenario: Proxy configuration correct
    Tool: Bash
    Steps: grep -A 5 "proxy" vite.config.ts
    Expected: Contains /api/v1 and localhost:8000
    Evidence: .sisyphus/evidence/task-2-proxy.txt
  ```

  **Commit**: YES | Message: `chore(config): add vite.config.ts with proxy and aliases` | Files: vite.config.ts

---

- [x] 3. Create TypeScript Types

  **What to do**: Create `src/types/chat.ts` and `src/types/api.ts` with complete TypeScript definitions for chat domain and API contracts.
  **Must NOT do**: Use `any` type, skip union type definitions for message types

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Foundation types, all code depends on this
  - Skills: `typescript` — Ensure strict typing
  - Omitted: `react` — Pure type definitions

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 9 | Blocked By: 2

  **References**:
  - Spec: WebSocket message types (clarification_request, progress_update, analysis_result)
  - Spec: API endpoints (POST /chat/messages, POST /chat/clarify, GET /chat/sessions)
  - Docs: `docs/BACKEND_STRUCTURE.md` for data models

  **Acceptance Criteria**:
  - [ ] `src/types/chat.ts` created with all message types
  - [ ] `src/types/api.ts` created with request/response types
  - [ ] No `any` types used
  - [ ] All message types have discriminated union (type field)
  - [ ] `npx tsc --noEmit` passes

  **QA Scenarios**:
  ```
  Scenario: Types file exists and compiles
    Tool: Bash
    Steps: ls src/types/*.ts && npx tsc --noEmit src/types/*.ts
    Expected: Files exist, compilation passes
    Evidence: .sisyphus/evidence/task-3-types-compile.log

  Scenario: No any types
    Tool: Bash
    Steps: grep -r ": any" src/types/ || echo "No any types found"
    Expected: "No any types found" or empty
    Evidence: .sisyphus/evidence/task-3-no-any.txt
  ```

  **Commit**: YES | Message: `feat(types): add chat and api type definitions` | Files: src/types/chat.ts, src/types/api.ts

---

- [x] 4. Create API Client

  **What to do**: Create `src/api/client.ts` with Axios instance, request/response interceptors for auth tokens and error handling.
  **Must NOT do**: Skip error handling, hardcode base URL (use env variable)

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Foundation, all API calls depend on this
  - Skills: `typescript`, `axios` — Proper typing and interceptors
  - Omitted: `react` — Pure HTTP client

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 9 | Blocked By: 2, 3

  **References**:
  - Spec: API endpoints (POST /chat/messages, POST /chat/clarify, GET /chat/sessions)
  - Pattern: `docs/WEBSOCKET_GUIDE.md` mentions auth patterns
  - Env: `VITE_API_BASE_URL` (default: /api/v1)

  **Acceptance Criteria**:
  - [ ] `src/api/client.ts` created with Axios instance
  - [ ] Reads baseURL from `import.meta.env.VITE_API_BASE_URL`
  - [ ] Request interceptor adds Authorization header with Bearer token
  - [ ] Response interceptor handles common errors (401, 403, 500)
  - [ ] TypeScript compiles without errors

  **QA Scenarios**:
  ```
  Scenario: API client compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/api/client.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-4-api-client.log

  Scenario: Imports axios correctly
    Tool: Bash
    Steps: grep "import axios" src/api/client.ts
    Expected: Match found
    Evidence: .sisyphus/evidence/task-4-axios-import.txt
  ```

  **Commit**: YES | Message: `feat(api): add axios client with interceptors` | Files: src/api/client.ts

---

### Wave 2: State & Router

- [x] 5. Create Zustand Store

  **What to do**: Create `src/store/chatStore.ts` with Zustand, immer middleware, and persist for message history. Include all required state and actions per spec.
  **Must NOT do**: Put immer outside persist (wrong order), skip type safety on actions

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Central state, critical correctness
  - Skills: `typescript`, `zustand` — Middleware patterns
  - Omitted: `react` — Store logic only

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 6, 7, 9, 13-18 | Blocked By: 3, 4

  **References**:
  - Spec: Required state (messages, currentSessionId, isProcessing, clarificationContext, disclaimerChecked)
  - Spec: Required actions (sendMessage, answerClarification, loadSession, clearSession)
  - Pattern: Zustand middleware order: `persist(immer((set) => ...))`
  - Docs: https://docs.pmnd.rs/zustand/guides/typescript

  **Acceptance Criteria**:
  - [ ] `src/store/chatStore.ts` created
  - [ ] Uses `create` from zustand with immer middleware
  - [ ] Uses `persist` middleware for localStorage persistence
  - [ ] All required state properties defined with types
  - [ ] All required actions implemented
  - [ ] Middleware order correct: persist(immer(...))

  **QA Scenarios**:
  ```
  Scenario: Store compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/store/chatStore.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-5-store-compile.log

  Scenario: Middleware order correct
    Tool: Bash
    Steps: grep -A 3 "persist" src/store/chatStore.ts | grep -A 2 "immer"
    Expected: Shows persist wrapping immer
    Evidence: .sisyphus/evidence/task-5-middleware-order.txt
  ```

  **Commit**: YES | Message: `feat(store): add zustand chat store with immer and persist` | Files: src/store/chatStore.ts

---

- [x] 6. Create Auth Hook

  **What to do**: Create `src/hooks/useAuth.ts` that checks authentication state and provides login/logout functions.
  **Must NOT do**: Implement full auth flow (login page out of scope), just the hook

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Router depends on this
  - Skills: `typescript`, `react` — Hook patterns
  - Omitted: `ui` — No UI in hook

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 19-21 | Blocked By: 5

  **References**:
  - Spec: Route guard redirects unauthenticated users to login
  - Pattern: localStorage token storage
  - Docs: React Router auth patterns

  **Acceptance Criteria**:
  - [ ] `src/hooks/useAuth.ts` created
  - [ ] Returns `isAuthenticated: boolean`
  - [ ] Returns `token: string | null`
  - [ ] Returns `login(token)` and `logout()` functions
  - [ ] Reads token from localStorage on mount

  **QA Scenarios**:
  ```
  Scenario: Auth hook compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/hooks/useAuth.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-6-auth-hook.log
  ```

  **Commit**: YES | Message: `feat(auth): add useAuth hook for token management` | Files: src/hooks/useAuth.ts

---

- [x] 7. Create Router Configuration

  **What to do**: Create `src/router/index.tsx` with React Router routes for /chat and /chat/history, with auth guard.
  **Must NOT do**: Skip auth guard, forget route parameters

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Navigation foundation
  - Skills: `typescript`, `react`, `react-router` — Route patterns
  - Omitted: `ui` — Route config only

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 19-21 | Blocked By: 5, 6

  **References**:
  - Spec: /chat (main), /chat/history (history), redirect / to /chat
  - Spec: Unauthenticated users → login page (assume /login exists)
  - Pattern: useAuth hook for guard

  **Acceptance Criteria**:
  - [ ] `src/router/index.tsx` created
  - [ ] Defines routes for /chat, /chat/history
  - [ ] Root / redirects to /chat
  - [ ] Auth guard redirects to /login if not authenticated
  - [ ] Uses React Router v7 createBrowserRouter or Routes component

  **QA Scenarios**:
  ```
  Scenario: Router compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/router/index.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-7-router-compile.log
  ```

  **Commit**: YES | Message: `feat(router): add route config with auth guard` | Files: src/router/index.tsx

---

- [x] 8. Create App.tsx

  **What to do**: Create `src/App.tsx` root component with Ant Design ConfigProvider for theming.
  **Must NOT do**: Skip ConfigProvider (breaks antd styling), forget CSS import

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: App root, affects all children
  - Skills: `typescript`, `react`, `antd` — Provider setup
  - Omitted: `ui` — Just provider wrapper

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 22 | Blocked By: 3

  **References**:
  - Spec: Primary color #1890ff (antd default)
  - Docs: https://ant.design/docs/react/customize-theme
  - Pattern: ConfigProvider with theme tokens

  **Acceptance Criteria**:
  - [ ] `src/App.tsx` created
  - [ ] Imports antd CSS (import 'antd/dist/reset.css')
  - [ ] Wraps app in ConfigProvider
  - [ ] Uses RouterProvider or Router from router/index

  **QA Scenarios**:
  ```
  Scenario: App compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/App.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-8-app-compile.log
  ```

  **Commit**: YES | Message: `feat(app): add root App component with Ant Design provider` | Files: src/App.tsx

---

### Wave 3: Hooks

- [x] 9. Create useChatWebSocket Hook

  **What to do**: Create `src/hooks/useChatWebSocket.ts` with native WebSocket, heartbeat (25s), auto-reconnect (max 5 attempts), and message type handling.
  **Must NOT do**: Use socket.io (spec says native WS), use useState for connection (useRef for StrictMode), forget cleanup

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Complex async logic, React StrictMode handling
  - Skills: `typescript`, `react`, `websockets` — WS patterns, useRef
  - Omitted: `ui` — Pure hook logic

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 19 | Blocked By: 3, 4, 5

  **References**:
  - Spec: Endpoint `wss://api.acmgflow.com/ws/chat/{sessionId}`
  - Spec: Heartbeat every 25s, timeout 30s
  - Spec: Message types (clarification_request, progress_update, analysis_result)
  - Pattern: React 19 StrictMode double-mount fix (useRef isMounted)
  - Docs: `docs/WEBSOCKET_GUIDE.md` for reconnect pattern

  **Acceptance Criteria**:
  - [ ] `src/hooks/useChatWebSocket.ts` created
  - [ ] Accepts sessionId parameter
  - [ ] Uses useRef for connection state (not useState)
  - [ ] Implements heartbeat: send ping every 25s
  - [ ] Implements reconnect: 5 attempts with exponential backoff (1s, 2s, 4s, 8s)
  - [ ] Handles message types per spec
  - [ ] Cleanup on unmount: close WS, clear intervals
  - [ ] Returns connection status and sendMessage function

  **QA Scenarios**:
  ```
  Scenario: WebSocket hook compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/hooks/useChatWebSocket.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-9-ws-compile.log

  Scenario: Uses useRef for connection
    Tool: Bash
    Steps: grep "useRef" src/hooks/useChatWebSocket.ts | head -3
    Expected: Shows useRef usage
    Evidence: .sisyphus/evidence/task-9-useref.txt
  ```

  **Commit**: YES | Message: `feat(ws): add useChatWebSocket hook with heartbeat and reconnect` | Files: src/hooks/useChatWebSocket.ts

---

- [x] 10. Create useFileUpload Hook

  **What to do**: Create `src/hooks/useFileUpload.ts` wrapper around react-dnd for drag-drop file upload with validation.
  **Must NOT do**: Use custom drag-drop implementation, skip file type/size validation

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: File handling needs safety
  - Skills: `typescript`, `react`, `react-dnd` — DnD patterns
  - Omitted: `ui` — Hook logic only

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 18 | Blocked By: 3

  **References**:
  - Spec: PDF only, max 10MB per file
  - Library: react-dnd already installed
  - Pattern: useDrag, useDrop hooks from react-dnd

  **Acceptance Criteria**:
  - [ ] `src/hooks/useFileUpload.ts` created
  - [ ] Uses react-dnd hooks
  - [ ] Validates file type (PDF only)
  - [ ] Validates file size (max 10MB)
  - [ ] Returns isDragging, files, addFiles, removeFile

  **QA Scenarios**:
  ```
  Scenario: File upload hook compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/hooks/useFileUpload.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-10-file-hook.log
  ```

  **Commit**: YES | Message: `feat(hooks): add useFileUpload with react-dnd` | Files: src/hooks/useFileUpload.ts

---

- [x] 11. Create useScrollToBottom Hook

  **What to do**: Create `src/hooks/useScrollToBottom.ts` for auto-scrolling message container to latest message with smooth animation.
  **Must NOT do**: Skip smooth scroll, scroll on every render (use deps)

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Simple hook
  - Skills: `typescript`, `react` — useRef, useEffect
  - Omitted: `ui` — Pure hook

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 19 | Blocked By: -

  **References**:
  - Spec: Auto-scroll to latest message with smooth animation
  - Pattern: useRef for container, scrollTo with behavior: 'smooth'

  **Acceptance Criteria**:
  - [ ] `src/hooks/useScrollToBottom.ts` created
  - [ ] Accepts dependency array (messages)
  - [ ] Uses smooth scroll behavior
  - [ ] Returns ref to attach to container

  **QA Scenarios**:
  ```
  Scenario: Scroll hook compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/hooks/useScrollToBottom.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-11-scroll-hook.log
  ```

  **Commit**: YES | Message: `feat(hooks): add useScrollToBottom with smooth animation` | Files: src/hooks/useScrollToBottom.ts

---

- [x] 12. Create useRelativeTime Hook

  **What to do**: Create `src/hooks/useRelativeTime.ts` for formatting ISO 8601 timestamps as relative time ("2 minutes ago").
  **Must NOT do**: Hardcode English strings (use i18n-ready format)

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Simple utility hook
  - Skills: `typescript` — Date math
  - Omitted: `react` — Pure function could work, but hook for reactivity

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: -

  **References**:
  - Spec: Timestamps stored as ISO 8601 in localStorage
  - Spec: Display as relative time ("2 minutes ago")
  - Pattern: Intl.RelativeTimeFormat or custom formatter

  **Acceptance Criteria**:
  - [ ] `src/hooks/useRelativeTime.ts` created
  - [ ] Accepts ISO 8601 string
  - [ ] Returns relative time string (e.g., "2分钟前")
  - [ ] Updates periodically (every minute)

  **QA Scenarios**:
  ```
  Scenario: Time hook compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/hooks/useRelativeTime.ts
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-12-time-hook.log
  ```

  **Commit**: YES | Message: `feat(hooks): add useRelativeTime for timestamp formatting` | Files: src/hooks/useRelativeTime.ts

---

### Wave 4: UI Components

- [x] 13. Create MessageBubble Component

  **What to do**: Create `src/components/chat/MessageBubble.tsx` that renders 4 message types with proper styling and timestamps.
  **Must NOT do**: Skip message type handling, use wrong colors (follow spec)

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Complex UI with conditional rendering
  - Skills: `typescript`, `react`, `antd` — Component patterns
  - Omitted: `ui-ux-pro-max` — Follow spec exactly, don't redesign

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 19 | Blocked By: 3, 5, 12

  **References**:
  - Spec: User bubble #e6f7ff (right-aligned), system bubble #f5f5f5 (left-aligned)
  - Spec: 4 types: clarification, progress, result, system
  - Spec: Markdown support (bold, code, links only)
  - Types: `src/types/chat.ts` ChatMessage union
  - Docs: react-markdown for rendering

  **Acceptance Criteria**:
  - [ ] `src/components/chat/MessageBubble.tsx` created
  - [ ] Renders all 4 message types correctly
  - [ ] User messages: right-aligned, #e6f7ff background
  - [ ] System messages: left-aligned, #f5f5f5 background
  - [ ] Shows timestamp with useRelativeTime
  - [ ] Uses react-markdown for content (limited plugins)
  - [ ] TypeScript compiles without errors

  **QA Scenarios**:
  ```
  Scenario: Message bubble compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/MessageBubble.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-13-bubble-compile.log

  Scenario: All message types handled
    Tool: Bash
    Steps: grep -E "case.*:|if.*type" src/components/chat/MessageBubble.tsx | wc -l
    Expected: At least 4 (one per type)
    Evidence: .sisyphus/evidence/task-13-types.txt
  ```

  **Commit**: YES | Message: `feat(components): add MessageBubble with 4 message types` | Files: src/components/chat/MessageBubble.tsx

---

- [x] 14. Create ClarificationButtons Component

  **What to do**: Create `src/components/chat/ClarificationButtons.tsx` with Ant Design buttons, default option highlighting, and 120s countdown with red flash at 30s.
  **Must NOT do**: Skip countdown, forget "推荐" tag on default

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Timer and conditional styling
  - Skills: `typescript`, `react`, `antd` — Timer patterns, conditional CSS
  - Omitted: `ui-ux-pro-max` — Follow spec styling exactly

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 19 | Blocked By: 3, 5

  **References**:
  - Spec: Ant Design Button (default type)
  - Spec: Default option: dashed border + "推荐" tag
  - Spec: 120s countdown, red flash at 30s
  - Types: `src/types/chat.ts` Option type

  **Acceptance Criteria**:
  - [ ] `src/components/chat/ClarificationButtons.tsx` created
  - [ ] Uses Ant Design Button components
  - [ ] Shows options horizontally
  - [ ] Default option has dashed border and "推荐" tag
  - [ ] Implements 120s countdown
  - [ ] Turns red and flashes at 30s remaining
  - [ ] Click triggers answerClarification action

  **QA Scenarios**:
  ```
  Scenario: Clarification buttons compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/ClarificationButtons.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-14-clarify-compile.log

  Scenario: Countdown logic present
    Tool: Bash
    Steps: grep -E "120|countdown|timer" src/components/chat/ClarificationButtons.tsx
    Expected: Shows countdown implementation
    Evidence: .sisyphus/evidence/task-14-countdown.txt
  ```

  **Commit**: YES | Message: `feat(components): add ClarificationButtons with countdown` | Files: src/components/chat/ClarificationButtons.tsx

---

- [x] 15. Create FileUploadZone Component

  **What to do**: Create `src/components/chat/FileUploadZone.tsx` with drag-drop area, blue highlight on drag, and file info display.
  **Must NOT do**: Skip drag visual feedback, forget file validation display

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: DnD UI with states
  - Skills: `typescript`, `react`, `react-dnd` — DnD visual patterns
  - Omitted: `ui-ux-pro-max` — Follow spec styling

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 18 | Blocked By: 3, 10

  **References**:
  - Spec: Drag area highlights blue on drag
  - Spec: Shows "已识别：中文文献（24页）"
  - Spec: PDF only support
  - Hook: `src/hooks/useFileUpload.ts`

  **Acceptance Criteria**:
  - [ ] `src/components/chat/FileUploadZone.tsx` created
  - [ ] Uses useFileUpload hook
  - [ ] Shows drag overlay with blue border
  - [ ] Displays uploaded file name and info
  - [ ] Validates PDF file type
  - [ ] Shows error for invalid files

  **QA Scenarios**:
  ```
  Scenario: File upload zone compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/FileUploadZone.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-15-upload-compile.log
  ```

  **Commit**: YES | Message: `feat(components): add FileUploadZone with drag-drop` | Files: src/components/chat/FileUploadZone.tsx

---

- [x] 16. Create ContextPanel Component

  **What to do**: Create `src/components/chat/ContextPanel.tsx` as the right-side panel (30% width) for displaying PDF context and evidence details.
  **Must NOT do**: Implement full PDF viewer (placeholder only), forget collapsible behavior

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Layout component
  - Skills: `typescript`, `react` — Layout patterns
  - Omitted: `antd` — Pure layout component

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 19 | Blocked By: 3

  **References**:
  - Spec: 30% width, collapsible
  - Spec: Shows PDF content when PMID link clicked
  - Note: PDF viewer implementation out of scope (use placeholder)

  **Acceptance Criteria**:
  - [ ] `src/components/chat/ContextPanel.tsx` created
  - [ ] Fixed 30% width on desktop
  - [ ] Hidden on mobile (< 768px)
  - [ ] Accepts content prop for display
  - [ ] Placeholder for PDF viewer

  **QA Scenarios**:
  ```
  Scenario: Context panel compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/ContextPanel.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-16-panel-compile.log
  ```

  **Commit**: YES | Message: `feat(components): add ContextPanel layout component` | Files: src/components/chat/ContextPanel.tsx

---

- [x] 17. Create ProgressSteps Component

  **What to do**: Create `src/components/chat/ProgressSteps.tsx` using Ant Design Steps to show workflow progress with current step highlighted.
  **Must NOT do**: Use custom step component (use antd Steps)

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Use antd component
  - Skills: `typescript`, `react`, `antd` — Steps component API
  - Omitted: `ui-ux-pro-max` — Standard antd styling

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 19 | Blocked By: 3

  **References**:
  - Spec: Ant Design Steps component
  - Spec: Current step highlighted
  - Docs: https://ant.design/components/steps

  **Acceptance Criteria**:
  - [ ] `src/components/chat/ProgressSteps.tsx` created
  - [ ] Uses Ant Design Steps component
  - [ ] Shows current step as active
  - [ ] Shows step descriptions
  - [ ] Updates based on progress prop

  **QA Scenarios**:
  ```
  Scenario: Progress steps compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/ProgressSteps.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-17-steps-compile.log

  Scenario: Uses antd Steps
    Tool: Bash
    Steps: grep "import.*Steps" src/components/chat/ProgressSteps.tsx
    Expected: Shows Steps import from antd
    Evidence: .sisyphus/evidence/task-17-antd-steps.txt
  ```

  **Commit**: YES | Message: `feat(components): add ProgressSteps with antd Steps` | Files: src/components/chat/ProgressSteps.tsx

---

- [x] 18. Create ChatInput Component

  **What to do**: Create `src/components/chat/ChatInput.tsx` with text input, file upload integration, disclaimer checkbox, and submit button.
  **Must NOT do**: Skip disclaimer checkbox, allow submit while processing

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Complex input with states
  - Skills: `typescript`, `react`, `antd` — Form patterns
  - Omitted: `ui-ux-pro-max` — Follow spec exactly

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 19 | Blocked By: 3, 5, 10, 15

  **References**:
  - Spec: Input fixed at bottom
  - Spec: Disclaimer checkbox (mandatory)
  - Spec: Disable input when isProcessing
  - Spec: Example text shown
  - Component: FileUploadZone integration

  **Acceptance Criteria**:
  - [ ] `src/components/chat/ChatInput.tsx` created
  - [ ] Text input with placeholder
  - [ ] Shows example text below input
  - [ ] Integrates FileUploadZone
  - [ ] Disclaimer checkbox (mandatory to submit)
  - [ ] Disabled state when isProcessing
  - [ ] Submit button triggers sendMessage

  **QA Scenarios**:
  ```
  Scenario: Chat input compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/ChatInput.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-18-input-compile.log

  Scenario: Disclaimer checkbox present
    Tool: Bash
    Steps: grep -i "disclaimer\|checkbox" src/components/chat/ChatInput.tsx
    Expected: Shows checkbox implementation
    Evidence: .sisyphus/evidence/task-18-disclaimer.txt
  ```

  **Commit**: YES | Message: `feat(components): add ChatInput with disclaimer and file upload` | Files: src/components/chat/ChatInput.tsx

---

### Wave 5: Pages & Integration

- [x] 19. Create ChatInterface Component

  **What to do**: Create `src/components/chat/ChatInterface.tsx` container with 70/30 layout, message list, and context panel integration.
  **Must NOT do**: Forget auto-scroll, skip responsive handling

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Complex container layout
  - Skills: `typescript`, `react`, `antd` — Layout composition
  - Omitted: `ui-ux-pro-max` — Follow spec layout exactly

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: 20, 21 | Blocked By: 5, 6, 7, 9, 11, 13-18

  **References**:
  - Spec: 70% messages, 30% context panel
  - Spec: Auto-scroll to latest message
  - Spec: Mobile hides context panel
  - Components: MessageBubble, ContextPanel, ChatInput
  - Hooks: useChatWebSocket, useScrollToBottom

  **Acceptance Criteria**:
  - [ ] `src/components/chat/ChatInterface.tsx` created
  - [ ] Implements 70/30 flex layout
  - [ ] Renders MessageBubble list from store
  - [ ] Shows ClarificationButtons when clarificationContext active
  - [ ] Integrates ContextPanel (30% width)
  - [ ] Integrates ChatInput at bottom
  - [ ] Auto-scrolls to latest message
  - [ ] Responsive: hides context panel on mobile
  - [ ] Shows Toast on disconnect

  **QA Scenarios**:
  ```
  Scenario: Chat interface compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/components/chat/ChatInterface.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-19-interface-compile.log

  Scenario: Layout uses 70/30
    Tool: Bash
    Steps: grep -E "70%|30%|flex.*0.*70" src/components/chat/ChatInterface.tsx
    Expected: Shows layout proportions
    Evidence: .sisyphus/evidence/task-19-layout.txt
  ```

  **Commit**: YES | Message: `feat(components): add ChatInterface container with 70/30 layout` | Files: src/components/chat/ChatInterface.tsx

---

- [x] 20. Create ChatPage

  **What to do**: Create `src/pages/ChatPage.tsx` that renders ChatInterface within page layout.
  **Must NOT do**: Skip layout wrapper, forget page title

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Page component
  - Skills: `typescript`, `react` — Page patterns
  - Omitted: `ui` — Container only

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: 22 | Blocked By: 19

  **References**:
  - Spec: /chat route main page
  - Component: ChatInterface
  - Router: Route config points here

  **Acceptance Criteria**:
  - [ ] `src/pages/ChatPage.tsx` created
  - [ ] Imports and renders ChatInterface
  - [ ] Sets page title (document.title)
  - [ ] TypeScript compiles

  **QA Scenarios**:
  ```
  Scenario: Chat page compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/pages/ChatPage.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-20-page-compile.log
  ```

  **Commit**: YES | Message: `feat(pages): add ChatPage for /chat route` | Files: src/pages/ChatPage.tsx

---

- [x] 21. Create ChatHistoryPage

  **What to do**: Create `src/pages/ChatHistoryPage.tsx` for /chat/history route showing list of past sessions.
  **Must NOT do**: Implement full history (use placeholder), forget link to session

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Page component
  - Skills: `typescript`, `react`, `antd` — List patterns
  - Omitted: `ui` — Use antd List component

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: 22 | Blocked By: 7

  **References**:
  - Spec: /chat/history standalone route
  - API: GET /chat/sessions?limit=20
  - Pattern: Ant Design List component

  **Acceptance Criteria**:
  - [ ] `src/pages/ChatHistoryPage.tsx` created
  - [ ] Uses Ant Design List component
  - [ ] Fetches sessions from API
  - [ ] Shows session list with timestamps
  - [ ] Clicking session loads it (link to /chat?session=xxx)
  - [ ] TypeScript compiles

  **QA Scenarios**:
  ```
  Scenario: History page compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/pages/ChatHistoryPage.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-21-history-compile.log
  ```

  **Commit**: YES | Message: `feat(pages): add ChatHistoryPage for /chat/history route` | Files: src/pages/ChatHistoryPage.tsx

---

- [x] 22. Create main.tsx Entry Point

  **What to do**: Create `src/main.tsx` application entry point with React 19 createRoot and StrictMode.
  **Must NOT do**: Use React 18 render, skip StrictMode

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: App entry point
  - Skills: `typescript`, `react` — Entry patterns
  - Omitted: `ui` — Pure setup

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: F1-F4 | Blocked By: 8, 20, 21

  **References**:
  - Spec: React 19.2.0
  - Pattern: createRoot from react-dom/client
  - Component: App.tsx

  **Acceptance Criteria**:
  - [ ] `src/main.tsx` created
  - [ ] Imports React 19 createRoot
  - [ ] Wraps App in StrictMode
  - [ ] Mounts to #root element
  - [ ] TypeScript compiles

  **QA Scenarios**:
  ```
  Scenario: Main entry compiles
    Tool: Bash
    Steps: npx tsc --noEmit src/main.tsx
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-22-main-compile.log

  Scenario: Uses createRoot
    Tool: Bash
    Steps: grep "createRoot" src/main.tsx
    Expected: Shows createRoot import and usage
    Evidence: .sisyphus/evidence/task-22-createroot.txt
  ```

  **Commit**: YES | Message: `feat(entry): add main.tsx with React 19 createRoot` | Files: src/main.tsx

---

### Wave 6: Final Verification

- [x] F1. TypeScript Compilation Audit

  **What to do**: Run full TypeScript compilation check on entire src/ directory.
  **Must NOT do**: Skip any files, ignore errors

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Verification only
  - Skills: `typescript` — Type checking

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: - | Blocked By: 22

  **Acceptance Criteria**:
  - [ ] `npx tsc --noEmit` passes with zero errors
  - [ ] No `any` types in new code

  **QA Scenarios**:
  ```
  Scenario: Full TypeScript check
    Tool: Bash
    Steps: npx tsc --noEmit 2>&1 | tee .sisyphus/evidence/f1-tsc.log
    Expected: Exit code 0, no errors in log
    Evidence: .sisyphus/evidence/f1-tsc.log

  Scenario: No any types
    Tool: Bash
    Steps: grep -r ": any" src/ --include="*.ts" --include="*.tsx" | wc -l
    Expected: 0
    Evidence: .sisyphus/evidence/f1-no-any.txt
  ```

  **Commit**: NO

---

- [x] F2. ESLint Audit

  **What to do**: Run ESLint on all source files.
  **Must NOT do**: Ignore warnings

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Verification only
  - Skills: `eslint` — Linting

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: - | Blocked By: 22

  **Acceptance Criteria**:
  - [ ] `npm run lint` passes with zero errors
  - [ ] No warnings treated as errors

  **QA Scenarios**:
  ```
  Scenario: ESLint check
    Tool: Bash
    Steps: npm run lint 2>&1 | tee .sisyphus/evidence/f2-lint.log
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/f2-lint.log
  ```

  **Commit**: NO

---

- [x] F3. Build Verification

  **What to do**: Run production build and verify output.
  **Must NOT do**: Skip build verification

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Verification only
  - Skills: `vite` — Build process

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: - | Blocked By: 22

  **Acceptance Criteria**:
  - [ ] `npm run build` completes successfully
  - [ ] `dist/index.html` exists
  - [ ] No build errors

  **QA Scenarios**:
  ```
  Scenario: Production build
    Tool: Bash
    Steps: npm run build 2>&1 | tee .sisyphus/evidence/f3-build.log
    Expected: Exit code 0, dist/ created
    Evidence: .sisyphus/evidence/f3-build.log

  Scenario: Check dist output
    Tool: Bash
    Steps: ls -la dist/index.html && ls dist/assets/*.js | wc -l
    Expected: index.html exists, at least one JS file
    Evidence: .sisyphus/evidence/f3-dist.txt
  ```

  **Commit**: NO

---

- [x] F4. Dev Server Smoke Test

  **What to do**: Start dev server and verify routes load.
  **Must NOT do**: Skip runtime verification

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Verification only
  - Skills: `bash` — Process management

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: - | Blocked By: 22

  **Acceptance Criteria**:
  - [ ] `npm run dev` starts without errors
  - [ ] `curl http://localhost:5173/chat` returns 200
  - [ ] Response contains expected content

  **QA Scenarios**:
  ```
  Scenario: Dev server starts
    Tool: Bash
    Steps: timeout 10 bash -c 'npm run dev & sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/chat'
    Expected: 200
    Evidence: .sisyphus/evidence/f4-server.log
  ```

  **Commit**: NO

---

## Final Verification Wave (4 parallel agents, ALL must APPROVE)

- [ ] FV1. Plan Compliance Audit — oracle
  - Review each TODO against spec requirements
  - Verify all deliverables present
  - Check no scope creep

- [ ] FV2. Code Quality Review — unspecified-high
  - Review all generated code for:
    - TypeScript strictness
    - No `any` types
    - Proper error handling
    - React best practices
    - Ant Design 6.0 patterns

- [V] FV3. Real Manual QA — unspecified-high (+ playwright if UI)
  - Start dev server
  - Navigate to /chat
  - Verify layout renders
  - Check responsive behavior
  - Verify WebSocket connection attempt

- [ ] FV4. Scope Fidelity Check — deep
  - Compare implementation against original spec
  - Verify all required features present
  - Confirm deferred features properly marked
  - Check acceptance criteria completeness

---

## Commit Strategy

### Commit Message Format
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types Used
- `chore(deps)`: Dependency installation
- `chore(config)`: Configuration files
- `feat(types)`: Type definitions
- `feat(api)`: API client
- `feat(store)`: State management
- `feat(auth)`: Authentication
- `feat(router)`: Routing
- `feat(hooks)`: Custom hooks
- `feat(components)`: UI components
- `feat(pages)`: Page components
- `feat(entry)`: Entry point

### Commit Granularity
- One commit per task (or logical grouping)
- Include all files modified by the task
- Reference task number in commit body if helpful

---

## Success Criteria

### Technical Success
- [ ] All TypeScript compiles without errors
- [ ] ESLint passes with zero errors
- [ ] Build creates working production bundle
- [ ] Dev server serves all routes correctly
- [ ] No `any` types in new code
- [ ] WebSocket connects and handles messages

### Functional Success
- [ ] /chat route loads and renders ChatInterface
- [ ] /chat/history route loads ChatHistoryPage
- [ ] Auth guard redirects unauthenticated users
- [ ] File upload accepts PDF via drag-drop
- [ ] Messages display with correct styling
- [ ] Clarification shows countdown and options
- [ ] Disclaimer checkbox blocks submit until checked
- [ ] Mobile responsive layout works

### Spec Compliance
- [ ] 70/30 layout implemented
- [ ] 4 message types handled
- [ ] 120s countdown with red flash at 30s
- [ ] WebSocket heartbeat (25s) and reconnect
- [ ] Ant Design components used correctly
- [ ] Zustand store with immer and persist
- [ ] All required state and actions present

### Quality Gates
- [ ] No console errors in dev mode
- [ ] No memory leaks (proper cleanup in hooks)
- [ ] Accessible (keyboard navigation, ARIA labels)
- [ ] Responsive (mobile, tablet, desktop)
- [ ] Performant (no unnecessary re-renders)

---

## Notes for Implementers

### Ant Design 6.0 Breaking Changes
- IE support dropped
- Semantic DOM changes in some components
- Some API naming changes (start/end vs left/right in Steps)
- Always check antd 6.0 docs, not 5.x

### React 19 StrictMode
- Components mount twice in development
- useChatWebSocket must use `useRef` for connection state
- Cleanup functions must be idempotent

### Zustand + Immer Order
```typescript
// CORRECT
const useStore = create(
  persist(
    immer((set) => ({
      // state and actions
    })),
    { name: 'chat-storage' }
  )
);
```

### WebSocket Auth
The spec doesn't define auth mechanism. Assume JWT in query param:
```
wss://api.acmgflow.com/ws/chat/{sessionId}?token={jwt}
```

If backend uses different auth, update useChatWebSocket accordingly.

### File Upload Constraints
- Max 10 files total
- Max 10MB per file
- PDF format only (client-side validation)
- Show error message for invalid files

### Markdown Rendering
Use react-markdown with rehype-sanitize:
```typescript
<ReactMarkdown rehypePlugins={[rehypeSanitize]}>
  {content}
</ReactMarkdown>
```
DOMPurify is supplementary for edge cases.

### Responsive Breakpoints
- Mobile: < 768px (hide context panel)
- Tablet: 768px - 1024px
- Desktop: > 1024px (full 70/30 layout)

---

**Plan Generated**: 2026-03-12
**Author**: Prometheus
**Review Status**: Pending implementation
