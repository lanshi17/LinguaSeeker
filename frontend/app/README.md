# App Router Pages

> Next.js 15 App Router pages that define the application's routing structure. Pages are thin orchestrators that compose feature components and layout primitives. Business logic lives in `src/features/`; pages only wire components to routes.

## Route Structure

```
app/
├── layout.tsx                     # Root layout: <html>, <body>, QueryProvider, NotificationToast
├── page.tsx                       # Root redirect → /pipeline
├── providers.tsx                  # QueryClientProvider (TanStack Query)
├── globals.css                    # Global styles (Tailwind base + custom)
│
├── (dashboard)/                   # Dashboard layout group (authenticated pages)
│   ├── layout.tsx                 # DashboardLayout wrapper (sidebar + top bar)
│   ├── pipeline/
│   │   ├── page.tsx               # /pipeline — New pipeline submission form
│   │   └── [runId]/page.tsx       # /pipeline/{runId} — Pipeline status view
│   ├── evidence/
│   │   └── page.tsx               # /evidence — Evidence search
│   └── chat/
│       ├── page.tsx               # /chat — Chat sessions list
│       └── [sessionId]/page.tsx   # /chat/{sessionId} — Single chat session
│
└── (auth)/                        # Auth layout group (public pages)
    ├── login/page.tsx             # /login — Login form
    └── register/page.tsx          # /register — Registration form
```

## Pages

### Root Page (`app/page.tsx`)

Server component that immediately redirects to `/pipeline`.

```typescript
import { redirect } from "next/navigation";
export default function RootPage() {
  redirect("/pipeline");
}
```

### Root Layout (`app/layout.tsx`)

Server component that wraps the entire app:
- `<html lang="en">` with `suppressHydrationWarning`
- `<body>` with `suppressHydrationWarning`
- `<QueryProvider>` for TanStack Query
- `<NotificationToast />` for global toast rendering
- Metadata: title "ACMG Lingua", description

### QueryProvider (`app/providers.tsx`)

Client component that initializes and provides `QueryClient`:

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30s before refetch
      retry: 1,                 // Retry once on failure
      refetchOnWindowFocus: false,
    },
  },
});
```

---

## Dashboard Group (`(dashboard)/`)

All routes in this group share the `DashboardLayout` (sidebar, top bar, connection status).

### Dashboard Layout (`(dashboard)/layout.tsx`)

Server component that wraps children in `<DashboardLayout>`:

```typescript
import { DashboardLayout } from "@/components/layout/DashboardLayout";

export default function Layout({ children }: { children: ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
```

### Pipeline Pages

#### `/pipeline` — New Pipeline Run

```typescript
import { PipelineSubmitForm } from "@/features/pipeline";
import { PageHeader } from "@/components/layout/PageHeader";

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="New Pipeline Run"
        description="Submit a document or search query to start the evidence extraction pipeline."
      />
      <PipelineSubmitForm />
    </div>
  );
}
```

**Components used:**
- `PageHeader` — title and description
- `PipelineSubmitForm` — source type selector, query/file upload, submit button

#### `/pipeline/[runId]` — Pipeline Status

```typescript
import { PipelineStatusView } from "@/features/pipeline";

interface PipelineRunPageProps {
  params: Promise<{ runId: string }>;
}

export default async function PipelineRunPage({ params }: PipelineRunPageProps) {
  const { runId } = await params;
  return <PipelineStatusView runId={runId} />;
}
```

**Components used:**
- `PipelineStatusView` — orchestrates `usePipelineStatus`, `PhaseTimeline`, `PhaseDetailCard`

**Dynamic route:** `runId` is extracted from the URL and passed to the status view.

### Evidence Page

#### `/evidence` — Evidence Search

```typescript
import { EvidenceSearchView } from "@/features/evidence-search";
import { PageHeader } from "@/components/layout/PageHeader";

export default function EvidencePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Search"
        description="Search evidence cards by gene, variant, disease, or PMID."
      />
      <EvidenceSearchView />
    </div>
  );
}
```

**Components used:**
- `PageHeader` — title and description
- `EvidenceSearchView` — form + results table with auto-load

### Chat Pages

#### `/chat` — Chat Sessions

```typescript
import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Chat Sessions" />
      <ChatView />
    </div>
  );
}
```

**Components used:**
- `PageHeader` — title only
- `ChatView` — full chat UI with conversation sidebar (no `processingRunId` or `sessionId` = standalone mode)

#### `/chat/[sessionId]` — Single Chat Session

```typescript
import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

interface ChatSessionPageProps {
  params: Promise<{ sessionId: string }>;
}

export default async function ChatSessionPage({ params }: ChatSessionPageProps) {
  const { sessionId } = await params;
  return (
    <div className="space-y-6">
      <PageHeader title="Chat" description={`Session: ${sessionId}`} />
      <ChatView sessionId={sessionId} />
    </div>
  );
}
```

**Components used:**
- `PageHeader` — title and session ID
- `ChatView` — single-session mode (no sidebar)

---

## Auth Group (`(auth)/`)

Public pages without the dashboard layout. Centered card layout.

### `/login` — Login

```typescript
import { LoginForm } from "@/features/auth";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <LoginForm />
    </div>
  );
}
```

**Components used:**
- `LoginForm` — email/password form, redirects to `/pipeline` on success

### `/register` — Registration

```typescript
import { RegisterForm } from "@/features/auth";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <RegisterForm />
    </div>
  );
}
```

**Components used:**
- `RegisterForm` — email/password/confirm form, redirects to `/login` on success

## Page Patterns

### Standard page structure

Every dashboard page follows this pattern:

```typescript
import { PageHeader } from "@/components/layout/PageHeader";
import { FeatureView } from "@/features/my-feature";

export default function MyPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="My Feature" description="What this page does" />
      <FeatureView />
    </div>
  );
}
```

### Dynamic routes with params

Next.js 15 App Router uses `Promise<{ param: string }>` for dynamic segments:

```typescript
interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <Component id={id} />;
}
```

### Server vs Client components

- **Pages are server components** by default (can use `async/await`, no `"use client"`)
- **Feature components are client components** (marked with `"use client"`)
- **Layouts are server components** (wrap client components)

## Extension Guide

### Adding a new dashboard page

1. Create `app/(dashboard)/my-page/page.tsx`
2. Add navigation item to `Sidebar.tsx`:

```typescript
const NAV_ITEMS: NavItem[] = [
  // ... existing items
  { label: "My Page", href: "/my-page", icon: MyIcon },
];
```

3. Create the feature module in `src/features/my-page/`
4. Compose the page:

```typescript
import { MyFeatureView } from "@/features/my-page";
import { PageHeader } from "@/components/layout/PageHeader";

export default function MyPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="My Page" />
      <MyFeatureView />
    </div>
  );
}
```

### Adding a new auth page

1. Create `app/(auth)/my-auth-page/page.tsx`
2. Use the centered card layout:

```typescript
export default function MyAuthPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <MyAuthForm />
    </div>
  );
}
```

### Adding route groups for different layouts

Create a new group directory with parentheses:

```
app/
├── (admin)/
│   ├── layout.tsx          # Admin-specific layout
│   └── settings/page.tsx
```

## Development

### Running the dev server

```bash
cd frontend
npm run dev
```

Open http://localhost:3000

### Building for production

```bash
cd frontend
npm run build
npm run start
```

### Type checking

```bash
cd frontend
npm run type-check
```

### Linting

```bash
cd frontend
npm run lint
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `next` | ^16.2.7 | App Router, server components, dynamic routes |
| `react` | ^18.3.0 | UI library |
| `@tanstack/react-query` | ^5.50.0 | Data fetching via `QueryProvider` |

## Testing

Page-level integration tests live in `frontend/tests/app/`.

```bash
cd frontend
npm run test -- --testPathPattern=app
```
