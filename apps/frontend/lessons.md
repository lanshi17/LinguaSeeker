# Frontend Implementation Lessons

## Project Overview
Multi-ACMG Frontend - React 19 + TypeScript + Vite application for ACMG-PS3 evidence intelligence system.

## Implementation Progress

### Completed Features

#### 1. TypeScript Types (src/types/)
- **auth.ts**: Authentication types for email registration, login, verification codes
- **task.ts**: Task management types including:
  - RequestStatus, PaperTaskStatus, ErrorCode, WarningCode
  - TaskRequest, PaperTask, LiteratureCandidate
  - CreateRequestPayload, RequestStatusResponse
  - EvidenceOutput, SentenceAlignment, BilingualContent

#### 2. API Services (src/services/)
- **authApi.ts**: Authentication API endpoints (login, register, send/verify code)
- **taskApi.ts**: Task management API endpoints:
  - createRequest, getRequestStatus, getCandidates
  - submitExecute, getPaperTaskStatus, reissueLogLink, uploadFile

#### 3. Pages Implemented (src/pages/)

##### Auth Pages (src/pages/auth/)
- **AuthPage.tsx**: Combined login/register page with email verification
  - Form validation (email format, password strength)
  - Verification code countdown (60s cooldown)
  - Toggle between login and register modes

##### Task Pages (src/pages/tasks/)
- **TaskCreatePage.tsx**: Interactive agent conversation for task creation
  - Max 2 clarification rounds as per PRD
  - Task order form with goal/disease/country/language fields
  - File upload support (PDF/DOCX, max 10 files, 50MB total)
  
- **CandidateSelectPage.tsx**: Literature candidate selection
  - Pagination (default 10/page, max 15/page)
  - Selection constraints (min 1, max 10)
  - File upload with SHA-256 deduplication
  
- **RequestMonitorPage.tsx**: Request-level progress monitoring
  - Real-time polling (3s interval)
  - Status visualization (queued/running/success/failed/partial_failed)
  - Error code mapping to Chinese messages
  - Log link reissue functionality

##### Result Pages (src/pages/results/)
- **LiteratureResultPage.tsx**: Dual-tab literature results
  - **Tab 1 - 对照阅读**: Bilingual side-by-side reading with entity highlighting
  - **Tab 2 - 证据判定**: ACMG PS3/BS3 conclusions and evidence list
  - Sync scroll between original and English panels
  - View modes: parallel/original-only/english-only

#### 4. Router Updates (src/router/index.tsx)
Added new routes:
- `/login`, `/register` - Authentication
- `/tasks/create` - Task creation with agent
- `/requests/:requestId/candidates` - Candidate selection
- `/requests/:requestId/monitor` - Request monitoring
- `/requests/:requestId/results/:paperTaskId` - Literature results

### Key Design Decisions

#### 1. Component Architecture
- Used functional components with React hooks
- Consistent error handling pattern (try-catch with ErrorResponse type)
- Loading states with spinner animations

#### 2. State Management
- Local component state with useState for form data
- URL parameters for request/paper IDs
- Polling mechanism for real-time status updates

#### 3. File Upload Strategy
- Client-side validation before upload (format, size)
- Progress tracking via XMLHttpRequest
- Server-side deduplication via SHA-256

#### 4. UI/UX Patterns
- Responsive design with CSS Grid/Flexbox
- Color-coded status badges
- Expandable sections for detailed information
- Consistent icon usage (Lucide React)

### Lessons Learned

#### 1. Type Safety
- Define strict TypeScript interfaces early
- Use discriminated unions for status types
- Avoid `any` type - always define proper types

#### 2. API Integration
- Always handle timeout and network errors gracefully
- Implement retry mechanisms for critical operations
- Use consistent error response format

#### 3. Performance
- Lazy load non-critical routes
- Implement proper cleanup for polling intervals
- Use CSS transforms for animations (GPU accelerated)

#### 4. User Experience
- Provide clear feedback for all user actions
- Show loading states for async operations
- Validate inputs client-side before API calls

### Pre-existing Issues (Not Caused by This Implementation)

1. **src/types/api.ts**: Line 23 - `integer` type not found (should be `number`)
2. **src/utils/errorHandler.ts**: Line 73 - Type error with window event handler
3. **tests/test-api-integration.ts**: Multiple import path errors
4. **src/pages/TaskStatusPage.tsx**: Type mismatch in error status

These errors existed before the MVP implementation and are unrelated to the new features.

### Build Verification Status

- [x] TypeScript types created
- [x] API services implemented
- [x] All MVP pages created
- [x] Routes updated
- [ ] CSS files created (pending)
- [ ] npm run lint (pending)
- [ ] npx tsc --noEmit (pending)
- [ ] npm run build (pending)

### Next Steps

1. Create CSS files for new pages:
   - TaskCreatePage.css
   - CandidateSelectPage.css
   - RequestMonitorPage.css
   - LiteratureResultPage.css

2. Run verification commands

3. Add authentication guards to protected routes

4. Implement PDF export functionality

5. Add unit tests for critical components
