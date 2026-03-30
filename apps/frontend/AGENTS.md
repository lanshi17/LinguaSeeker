# AGENTS.md - Frontend Development Guide

## 1. Project Overview

**Multi-ACMG Frontend** - React 19 + TypeScript + Vite application for ACMG-PS3 evidence intelligence system.

### 1.1 Tech Stack
- **Framework**: React 19.2.0 with TypeScript 5.9.3
- **Build Tool**: Vite (rolldown-vite@7.2.5)
- **Routing**: React Router DOM 7.13.0
- **State**: Zustand 5.0.10
- **Icons**: Lucide React
- **Styling**: CSS with CSS Variables (globals.css)

## 2. Build/Lint Commands

```bash
# Development
npm run dev              # Start dev server on port 5173

# Build
npm run build            # Production build (outputs to dist/)
npm run preview          # Preview production build

# Linting
npm run lint             # Run ESLint on all files
npx tsc --noEmit         # Type-check without emitting

# Utilities
npm run check-backend    # Check backend connectivity
npm run diagnose         # Print API diagnostics (run in browser console)
```

### 2.1 Test Commands
```bash
npm run test:run         # Run Vitest once
npx playwright test -c playwright.task12.config.cjs --reporter=line
```

Use Vitest for component/store tests and Playwright for the focused Task 12 E2E coverage.

## 3. Code Style Guidelines

### 3.1 Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Files | kebab-case | `document-reader.tsx` |
| Components | PascalCase | `DocumentReaderPage` |
| Variables/Functions | camelCase | `handleUpload` |
| CSS Classes | kebab-case | `evidence-card` |
| Interfaces/Types | PascalCase | `TaskStatusResponse` |
| Constants | UPPER_SNAKE_CASE | `API_BASE_URL` |

### 3.2 Import Order
1. React imports
2. Third-party libraries (react-router-dom, lucide-react)
3. Local absolute imports (@/components, @/utils)
4. Local relative imports (../services, ../types)
5. Type-only imports last with `import type`

```typescript
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, CheckCircle } from 'lucide-react';
import api from '../services/api';
import type { TaskStatusResponse } from '../types/api';
```

### 3.3 TypeScript Configuration
- **Target**: ES2022
- **Strict Mode**: OFF (`"strict": false` in tsconfig.app.json)
- **Module**: ESNext with Bundler resolution
- **JSX**: react-jsx (no React import needed for JSX)

### 3.4 Component Patterns
```typescript
// Functional component with explicit return type
const ComponentName: React.FC<PropsType> = ({ prop1, prop2 }) => {
  // Implementation
};

export default ComponentName;
```

### 3.5 Error Handling
- Use global error handler: `initGlobalErrorHandler()` in main.tsx
- API errors: Check `ErrorResponse` type with `detail` field
- Network errors: Handle fetch abort/timeout in api.ts
- NEVER use empty catch blocks

### 3.6 CSS/Styling
- Use CSS custom properties from globals.css
- Component-specific styles in separate `.css` files
- Responsive design with media queries
- No CSS-in-JS libraries (pure CSS)

## 4. Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── layout/         # Layout components (Navbar, etc.)
│   └── report/         # Report-specific components
├── pages/              # Page components (route handlers)
├── services/           # API service layer (api.ts)
├── types/              # TypeScript type definitions
│   ├── api.ts         # API response types
│   └── report.ts      # Report data types
├── hooks/              # Custom React hooks
├── utils/              # Utility functions
├── router/             # Route configuration
├── config/             # Configuration files
└── assets/             # Static assets and global CSS
```

## 5. API Integration

All API calls go through `src/services/api.ts`:

```typescript
// Import API functions
import { healthCheck, uploadPdf, getTaskStatus } from '../services/api';

// Use with proper error handling
try {
  const result = await getTaskStatus(taskId);
} catch (error) {
  // error is ErrorResponse type with 'detail' field
}
```

### 5.1 Environment Variables
- `VITE_API_BASE_URL` - Backend API URL (default: /api/v1)
- Defined in `.env`, `.env.local`, `.env.production`

## 6. Implementation Contract

All frontend work must follow these product specifications (priority order):

1. [docs/PRD.md](docs/PRD.md)
2. [docs/FRONTEND_GUIDELINES.md](docs/FRONTEND_GUIDELINES.md)
3. [docs/APP_FLOW.md](docs/APP_FLOW.md)
4. [docs/BACKEND_STRUCTURE.md](docs/BACKEND_STRUCTURE.md)
5. [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)

### 6.1 MVP Scope
**In Scope:**
- Login/Register (email verification)
- Task creation (Agent conversation + form)
- Literature candidate page (pagination, selection)
- Request monitoring (aggregated progress)
- Literature result page (dual-tab: bilingual reading + evidence judgment)
- PDF export entry

**Out of Scope:**
- Quality assessment pages
- Non-PubMed data sources

### 6.2 Hard Requirements
1. **Evidence Explainability**: Bilingual comparison with simultaneous highlighting
2. **Task Flow Transparency**: Clear execution path and failure reasons
3. **Constraint Validation**: Enforce selection limits, upload restrictions

## 7. Critical Constraints

### 7.1 Upload Limits (Client-side)
- Formats: PDF, DOCX only
- Max files: 10
- Single file: ≤10MB
- Total size: ≤50MB

### 7.2 Selection Limits
- Max candidates: 15
- Pagination: default 10/page, max 15/page
- User selection: min 1, max 10

### 7.3 Agent Clarification
- Max rounds: 2
- Task fields: `goal`, `disease`, `country`, `language`

## 8. Error Codes to Handle

Critical error codes the UI must recognize:
- `INPUT_INVALID`
- `FILE_TOO_LARGE`
- `FILE_TYPE_UNSUPPORTED`
- `FILE_DUPLICATE`
- `FETCH_NO_RESULT`
- `PARSE_FAILED`
- `TRANSLATION_FAILED`
- `EVIDENCE_EXTRACTION_FAILED`
- `ACMG_PARSE_FAILED`
- `INTERNAL_ERROR`

Warning (non-blocking): `HGVS_AUTOCORRECT_FAILED`

## 9. Development Rules

### 9.1 Prohibited
- ❌ Using `any` type
- ❌ Direct DOM manipulation
- ❌ Hardcoded sensitive data
- ❌ Unapproved third-party libraries
- ❌ Breaking existing functionality

### 9.2 Required
- ✅ All data must have TypeScript types
- ✅ Use DOMPurify for HTML sanitization
- ✅ Responsive design
- ✅ JSDoc for public functions
- ✅ Empty values display as "—"

## 10. State Visualization

### Request-level States (page top)
`queued` → `running` → `partial_failed` | `failed` | `success`

### Paper-level States (list)
`queued` → `running` → `success` | `failed`

Rules:
- `partial_failed`: ≥1 success AND ≥1 failed
- Duplicate files show `success` with "reused/skipped" tag

## 11. Log Link (log_link) Rules
1. Signed URL, valid for 24h
2. Provide "reissue" button after expiration
3. Rate limit: 1/minute per task_id
4. Any logged-in user can trigger reissue

## 12. Verification Checklist

Before completing work:
- [ ] `npm run lint` passes
- [ ] `npx tsc --noEmit` passes (no type errors)
- [ ] `npm run build` succeeds
- [ ] Follows naming conventions
- [ ] Proper error handling implemented
- [ ] Responsive design verified

## 13. State Management

**Library**: Zustand 5.0.10

**Architecture**:
- `src/store/appStore.ts` defines the unified `useAppStore` store for request polling, PubMed candidate fetching, and shared UI state.
- `src/store/index.ts` is the public export surface for `useAppStore`, `useTaskFlowStore`, and `useToastStore`.
- Keep task-creation flow state in `useTaskFlowStore`; use `useAppStore` for cross-page request/candidate state; use `useToastStore` for global notifications rendered by `NotificationToast`.

**Usage**:
```typescript
import { useAppStore } from '@/store';

const currentRequest = useAppStore((state) => state.currentRequest);
const requestFilters = useAppStore((state) => state.ui.requestFilters);
const fetchRequest = useAppStore((state) => state.fetchRequest);
```

**Selectors and updates**:
- Prefer selector-based subscriptions (`useAppStore((state) => state.ui.selectedPmids)`) instead of reading the whole store object.
- When updating nested UI state, use the existing store actions (`setTaskFilter`, `setRequestFilter`, `togglePmidSelection`, `togglePaperTaskExpand`) rather than mutating `ui` directly.
- For toast actions, select stable callbacks such as `useToastStore((state) => state.pushToast)` inside effects to avoid rerender loops.

**Current `useAppStore` responsibilities**:
- Request status fetch + request polling lifecycle
- PubMed candidate search results
- Shared UI state for filters, PMID selection, and paper-task expansion
- Store reset that also clears active polling intervals

**Polling rules**:
- Start polling through store actions and always stop it on unmount/cleanup.
- Request polling must stop on terminal statuses: `success`, `failed`, `partial_failed`.
- Do not add duplicate intervals for the same request key.

**DevTools**:
- If store inspection is needed during debugging, use the browser React/Zustand tooling available for the running app and verify selected slices rather than relying on whole-store logging.
