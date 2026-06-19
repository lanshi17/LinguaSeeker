# App Router Pages

> Next.js 15 App Router pages. Thin shells composing feature components; logic lives in `src/features/`.

## Route Structure

```
app/
├── layout.tsx                   Root layout: QueryProvider, NotificationToast
├── page.tsx                     Redirect -> /chat
├── providers.tsx                QueryClientProvider (TanStack Query)
├── globals.css                  Tailwind base + global styles
├── api/
│   └── auth/
│       ├── login/route.ts       POST — password auth, sets ce_session cookie (HMAC-SHA256)
│       └── logout/route.ts      POST — clears ce_session cookie
├── (auth)/
│   ├── login/page.tsx           /login — LoginForm
│   └── register/page.tsx        /register — RegisterForm
└── (dashboard)/
    ├── layout.tsx               DashboardLayout wrapper
    ├── pipeline/
    │   ├── page.tsx             /pipeline — PipelineSubmitForm + RunHistory (two-column grid)
    │   └── [runId]/page.tsx     /pipeline/:runId — PipelineStatusView (async, Promise params)
    ├── evidence/
    │   ├── page.tsx             /evidence — EvidenceSearchView (custom header with BookOpen icon)
    │   └── detail/page.tsx      /evidence/detail — EvidenceDetailView (searchParams: evidenceId, groupId, view)
    └── chat/
        ├── page.tsx             /chat — ChatView (full-viewport negative-margin layout)
        └── [sessionId]/page.tsx /chat/:sessionId — ChatView (async, Promise params, PageHeader)
```

## Patterns

- **Dashboard pages**: Typically `<PageHeader />` or a custom icon header + `<FeatureComponent />` in `<div className="space-y-6">`.
- **Dynamic routes**: Next.js 15 uses `Promise<{ param: string }>` for `params`; pages are `async`.
- **Search params**: Next.js 15 uses `Promise<Record<string, string | undefined>>` for `searchParams`; pages are `async`.
- **Auth pages**: Centered card layout over gray background.
- **API routes**: `app/api/auth/` handles session-based password auth (cookie `ce_session`, 8-hour expiry, HMAC-SHA256 signed).
- **Server vs Client**: Pages/layouts are server components; feature components are client components.
- **Chat pages**: Use negative-margin layout (`-mx-4 -mt-4`) to extend to full viewport height.

## Adding a New Page

1. Create `app/(dashboard)/route/page.tsx`.
2. Add nav item to `Sidebar.tsx` `NAV_ITEMS`.
3. Create the feature module in `src/features/`.