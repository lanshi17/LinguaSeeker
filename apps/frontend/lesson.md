2026-03-29 - Chat interaction contract variants and abort behavior need explicit component-level handling
- Symptom: clarification flow could mis-handle backend M2 variants where `clarification_question` is returned instead of `question`, or where `task_form` arrives with `task_form_ready` semantics different from legacy `ready` usage.
- Root cause: `AgentClarificationChat` originally assumed a narrower response shape in both start/respond branches and accepted task form by raw presence, which can over-accept payloads.
- Fix: introduced shared helpers in `src/components/chat/agent-clarification-chat.tsx`:
  - `pickQuestion(...)` to resolve question text from `question` or `clarification_question`
  - `hasReadyTaskForm(...)` to gate task-form acceptance on explicit ready signals
- Symptom: no request-cancellation safety when user restarts mid-request or component unmounts.
- Root cause: start/respond calls were issued without `AbortController`, despite service layer already supporting `ApiCallOptions.signal`.
- Fix: added component-scoped `AbortController` lifecycle management:
  - pass `{ signal }` to `interactionStart` and `interactionRespond`
  - abort in-flight calls on restart and unmount
  - treat abort exceptions as expected cancellation (no error toast/no error transcript append)
- Test/verification notes:
  - Added targeted RED→GREEN tests in `src/components/chat/agent-clarification-chat.test.tsx` for contract variants and abort wiring
  - Verified with focused test slices, type-check, lint, build, and changed-file diagnostics
- Prevention:
  - for compatibility-sensitive API surfaces, centralize response interpretation helpers and reuse them in all call branches
  - when API wrapper supports `signal`, wire abort semantics at component-level interactions that can be restarted/cancelled

2026-03-29 - Expert-feedback UX should be state-derived, not static text
- Symptom: `/tasks/new` had confirmation and branch controls, but no focused panel guiding users on the immediate next action when state changed (unconfirmed, confirmed-no-files, confirmed-with-files).
- Root cause: guidance was implicit across scattered labels/buttons rather than a single synthesized review surface.
- Fix: added `buildExpertFeedback(...)` in `src/pages/tasks/task-new-page.tsx` to derive concise hints from existing state (`taskForm`, `interactionRound`, `confirmedRequestId`, `files.length`) and render them in an `Expert feedback` panel.
- Test/verification notes:
  - Added RED→GREEN coverage in `src/pages/tasks/__tests__/task-new-page.test.tsx` for panel rendering and confirmation-first guidance.
  - Verified with targeted task/chat tests plus type-check, lint, build, and changed-file diagnostics.
- Prevention:
  - for multi-step flows, derive user guidance from authoritative state in one place so UX messaging stays synchronized with workflow gates.

2026-03-29 - Actionable guidance controls must avoid selector collisions with existing primary actions
- Symptom: after adding feedback shortcuts, tests targeting the existing `/Go to candidates/i` button began failing due multiple matched elements.
- Root cause: new feedback action reused text too close to the primary branch button label, making role/name queries ambiguous.
- Fix:
  - kept feedback actions but renamed the feedback candidate shortcut label to a distinct string (`Open candidates shortcut`), preserving semantic intent while restoring deterministic selectors.
  - retained the existing primary branch action label unchanged to avoid breaking established UX/tests.
- Test/verification notes:
  - added RED→GREEN coverage for `Confirm now` in `src/pages/tasks/__tests__/task-new-page.test.tsx` and reran task/chat regression slices.
  - confirmed with type-check, lint, build, and changed-file diagnostics.
- Prevention:
  - when adding secondary actions near existing controls, proactively choose non-overlapping accessible names and assert them explicitly in tests.
