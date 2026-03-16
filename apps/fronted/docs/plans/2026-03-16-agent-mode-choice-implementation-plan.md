# Agent Mode Choice + Graph Console (MVP) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an agent-first mode choice (documents vs graph) and a new `/graph` console aligned to `api_docs/openapi.json`.

**Architecture:** Extend Zustand task flow store with `entryMode`, gate chat start until a mode is chosen, and add a new Graph Console page that calls the two OpenAPI-defined graph endpoints and renders the JSON response.

**Tech Stack:** React 19 + TypeScript + Vite + React Router + Zustand; existing `src/services/http.ts` and `src/services/api.ts`.

---

### Task 1: Add entryMode to task flow store

**Files:**
- Modify: `src/store/useTaskFlowStore.ts`

**Step 1: Implement state + setter**
- Add `entryMode: 'documents' | 'graph' | null`
- Add `setEntryMode(entryMode)`

**Step 2: Type-check**
Run: `npx tsc --noEmit`
Expected: PASS

### Task 2: Gate clarification chat with agent-first mode choice

**Files:**
- Modify: `src/components/chat/agent-clarification-chat.tsx`
- Modify: `src/components/chat/agent-clarification-chat.css`

**Step 1: Render assistant prompt + quick replies when entryMode is null**
- Two buttons: documents / graph
- On click: append user message; set entryMode; navigate to `/graph` if graph

**Step 2: Gate Start**
- Start disabled until entryMode selected
- Restart clears entryMode

**Step 3: Lint + type-check**
Run: `npm run lint` and `npx tsc --noEmit`
Expected: PASS

### Task 3: Add Graph Console page and route

**Files:**
- Create: `src/pages/graph/graph-page.tsx`
- Create: `src/pages/graph/graph-page.css`
- Modify: `src/router/index.tsx`
- Modify: `src/components/layout/app-shell.tsx`

**Step 1: Add API wrappers**
- Modify: `src/services/api.ts`
- Add:
  - `getEvidenceGraphStats()` -> `GET /evidence/graph/stats`
  - `resyncEvidenceDocument(documentId)` -> `POST /evidence/sync/document/{document_id}`

**Step 2: Implement `/graph` UI**
- Graph Stats section (refresh)
- Resync section (document_id input + button)
- Render JSON response in `<pre>`

**Step 3: Add route + nav**
- Route: `/graph`
- AppShell nav link: Graph

**Step 4: Build verification**
Run: `npm run build`
Expected: exit 0

### Task 4: End-to-end verification

**Step 1: Lint**
Run: `npm run lint`
Expected: 0 errors

**Step 2: Type-check**
Run: `npx tsc --noEmit`
Expected: 0 errors

**Step 3: Build**
Run: `npm run build`
Expected: exit 0
