# App Router Pages

> Next.js 15 App Router pages. Thin shells composing feature components; logic lives in `src/features/`.

## Route Structure

```
app/
├── layout.tsx                   Root layout: QueryProvider, NotificationToast
├── page.tsx                     Redirect -> /pipeline
├── providers.tsx                QueryClientProvider (TanStack Query)
├── globals.css                  Tailwind base + global styles
├── (auth)/
│   ├── login/page.tsx           /login — LoginForm
│   └── register/page.tsx        /register — RegisterForm
└── (dashboard)/
    ├── layout.tsx               DashboardLayout wrapper
    ├── pipeline/
    │   ├── page.tsx             /pipeline — PipelineSubmitForm
    │   └── [runId]/page.tsx     /pipeline/:runId — PipelineStatusView
    ├── evidence/
    │   ├── page.tsx             /evidence — EvidenceSearchView
    │   └── detail/page.tsx      /evidence/detail — EvidenceDetailView
    └── chat/
        ├── page.tsx             /chat — ChatView (standalone)
        └── [sessionId]/page.tsx /chat/:sessionId — ChatView (single session)
```

## Patterns

- **Dashboard pages**: `<PageHeader />` + `<FeatureComponent />` in `<div className="space-y-6">`.
- **Dynamic routes**: Next.js 15 uses `Promise<{ param: string }>` for `params`; pages are async.
- **Auth pages**: Centered card layout.
- **Server vs Client**: Pages/layouts are server components; feature components are client components.

## Adding a New Page

1. Create `app/(dashboard)/route/page.tsx`.
2. Add nav item to `Sidebar.tsx` `NAV_ITEMS`.
3. Create the feature module in `src/features/`.