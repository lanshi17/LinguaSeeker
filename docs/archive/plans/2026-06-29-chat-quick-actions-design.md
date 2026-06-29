# Chat Quick Actions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-29
**Completed:** 2026-06-29

**Goal:** Make chat welcome quick actions trigger the right product workflow instead of always sending a plain prompt.

**Architecture:** `WelcomeBlock` owns the visible quick-action catalog and emits a typed action payload. `FullChatView` interprets the payload: pipeline starts still send a structured chat message, while upload/search/review shortcuts navigate directly to existing pages. `SingleSessionChat` keeps a send-message fallback because it does not own the dashboard router context.

**Tech Stack:** React 18, React Router, TypeScript strict mode, Vitest + Testing Library.

---

### Task 1: Type Welcome Quick Actions

**Files:**
- Modify: `frontend/src/features/chat/components/WelcomeBlock.tsx`
- Test: `frontend/tests/features/chat/WelcomeBlock.test.tsx`

**Steps:**
1. Add a failing test that clicks "Search evidence base" and expects `onPick` to receive `{ kind: "navigate", to: "/evidence" }`.
2. Add `WelcomeAction` as a discriminated union with `send-message` and `navigate`.
3. Change `SuggestionChip.message` to `SuggestionChip.action`.
4. Run the focused test and make it pass.

### Task 2: Wire Full Chat Navigation

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx`
- Modify: `frontend/src/features/chat/components/useBubbleItems.tsx`

**Steps:**
1. Pass an `onWelcomeAction` callback into `useBubbleItems`.
2. In `FullChatView`, send chat messages for `send-message` actions and call `navigate(action.to)` for navigation actions.
3. Keep the existing `handleSendMessage` code path for pipeline quick start.
4. Run focused chat tests and type-check.

### Task 3: Keep Single Session Fallback

**Files:**
- Modify: `frontend/src/features/chat/components/SingleSessionChat.tsx`

**Steps:**
1. Update `handleQuickAction` to accept `WelcomeAction`.
2. For `send-message`, send the action message.
3. For `navigate`, send `fallbackMessage` when present.
4. Run focused chat tests, `bun run type-check`, and `bun run lint`.
