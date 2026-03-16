- React 19 + TypeScript + Vite alias resolution: `npx tsc --noEmit` on single files fails without `--project tsconfig.json` because path aliases like `@/` are defined in the project config. Run from the root instead.
- Component-specific CSS matches Ant Design styling via custom classes like `.message-bubble.clarification` combined with Lucide icons.
- ClarificationButtons implemented: antd@6.3.2 installed for Button component; CSS keyframe animation 'flash' used for 30s red warning threshold; used setInterval with functional state update to safely track 120s countdown.
- ALWAYS ensure you are writing to the active worktree (`worktrees/chat-first-acmg/...`) rather than the base repository directory to avoid misplacing artifacts.

### Task 21: ChatHistoryPage Component

**Created**: `src/pages/ChatHistoryPage.tsx` (106 lines)

**Implementation Details**:
- Uses Ant Design `List` component with custom `renderItem` for session display
- Fetches from `GET /chat/sessions?limit=20` using existing `ListSessionsResponse` type
- Implements inline relative time hook (`useRelativeTimeForSession`) with 60-second auto-refresh
- Session titles use truncated session ID format: `会话 {id.slice(0,8)}`
- Empty state handled via List's `locale` prop: "暂无聊天记录"
- Links format: `/chat?session={sessionId}` using React Router's `Link` component
- Error handling uses Ant Design `message.error()` API

**Key Patterns**:
1. **Relative Time**: Implemented custom hook rather than importing from `src/hooks/useRelativeTime.ts` because that hook takes `isoTimestamp` as parameter directly (not returning a formatter function)
2. **Session Title Logic**: Simple fallback pattern checks `messages.length > 0`, defaults to "Untitled Session"
3. **Loading State**: Centered spinner with padding, consistent with other page patterns
4. **API Error Handling**: Console error + user-facing message.error() notification

**TypeScript Verification**: ✅ Compiles cleanly (only pre-existing taskStore:251 error remains)

**No TODOs/FIXMEs**: All functionality implemented completely per spec

**Atlas Note (Task 21 Review)**: ChatHistoryPage duplicates `useRelativeTime` hook logic (lines 76-106) instead of importing from `src/hooks/useRelativeTime.ts`. The existing hook signature `useRelativeTime(isoTimestamp: string): string` matches requirements exactly. This is code duplication but functionally correct. Future tasks should import existing hooks when signatures match.

### Task 22: main.tsx Entry Point (Single Task - Part 1)

**Modified**: `src/main.tsx` (12 lines, refactored from 18 lines)

**Changes Made**:
1. Replaced deprecated React 18 pattern with React 19 `createRoot` API
2. Removed broken import: `initGlobalErrorHandler()` from non-existent `utils/errorHandler.ts`
3. Removed obsolete `BrowserRouter` wrapper (App.tsx now uses RouterProvider internally)
4. Fixed CSS import path: `assets/globals.css` → `index.css` (actual file location)
5. Preserved `NotificationToast` component (required by notificationStore system)

**React 19 Pattern Used**:
```typescript
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
```

**Architecture Decision**:
- Old main.tsx had BrowserRouter wrapping AppRoutes (React Router v5 pattern)
- New App.tsx (Task 8) uses RouterProvider with createBrowserRouter (React Router v7 pattern)
- No need for BrowserRouter wrapper at root level anymore

**Verification**: 
- ✅ `grep "createRoot" src/main.tsx` shows import + usage
- ✅ TypeScript compiles cleanly: `npx tsc --noEmit --project tsconfig.app.json` (no main.tsx errors)
- ✅ Only pre-existing taskStore:251 error remains

**Key Learning**: When App.tsx uses RouterProvider, main.tsx should NOT wrap with BrowserRouter. The router configuration (Task 7) is passed to RouterProvider, not BrowserRouter.

### Task 23: Router Placeholder Component Replacement (ESLint Fast Refresh Fix)

**Modified**: `src/router/index.tsx` (54 lines, reduced from 68 lines)

**Changes Made**:
1. Added named imports for ChatPage and ChatHistoryPage after line 2:
   - `import { ChatPage } from '@/pages/ChatPage';`
   - `import { ChatHistoryPage } from '@/pages/ChatHistoryPage';`
2. Removed placeholder component definitions (lines 22-32):
   - Removed inline `const ChatPage = () => { return <div>Chat Page</div>; };`
   - Removed inline `const ChatHistoryPage = () => { return <div>Chat History</div>; };`
3. KEPT ProtectedRoute component (lines 8-16) - this is the auth guard, not a placeholder

**ESLint Fast Refresh Error Resolution**:
- **Before**: 3 Fast refresh errors on lines 8, 22, 30
- **After**: 1 Fast refresh error on line 10 (ProtectedRoute - separate task for moving to separate file)
- Errors on lines 22 and 30 (placeholder components) ✅ **RESOLVED**

**Export Pattern Verification**:
- ChatPage exports as named export: `export const ChatPage: React.FC = () => {...}`
- ChatHistoryPage exports as named export: `export const ChatHistoryPage: React.FC = () => {...}`
- Router imports both as named imports using path alias `@/pages/`

**TypeScript Compilation**: ✅ Passes cleanly with only pre-existing taskStore:251 error

**Critical Distinction**:
ProtectedRoute on line 10 is a FUNCTIONAL auth guard component, NOT a placeholder. ESLint wants it moved to a separate file, but this is a separate Wave 6 task. This task only fixed the placeholder components that were always meant to be replaced.

**Git Verification**:
- Clean diff: +2 imports, removed 14 lines of placeholder code
- Router configuration (lines ~31-52) unchanged
- ProtectedRoute component preserved
