# Documentation Index

Project documentation is organized by lifecycle status.

```text
docs/
├── README.md
├── active/           # In-progress implementation plans and working notes
├── planned/          # Planned work that has not started
├── codereview/       # Active code reviews (empty when all reviews are resolved)
├── archive/
│   ├── plans/        # Completed or superseded plans
│   └── codereview/   # Completed code reviews
└── templates/        # Reusable documentation templates
```

## Classification Rules

- `planned/`: planned work that has not started.
- `active/`: in-progress implementation plans and working notes.
- `codereview/`: active code review reports and review follow-ups.
- `archive/plans/`: completed or superseded plans.
- `archive/codereview/`: completed code reviews whose findings are resolved or no longer active.
- `templates/`: reusable documentation templates.

## Naming Convention

Use `YYYY-MM-DD-<kebab-case-description>.md` for new documents.

## Active Plans

| date | title | status/PR |
|---|---|---|
| 2026-05-09 | [PRD](active/PRD.md) | active — dual extraction scope |
| 2026-05-09 | [Application Flow](active/APP_FLOW.md) | active — dual extraction scope |
| 2026-05-09 | [Technology Stack](active/TECH_STACK.md) | active — dual extraction scope |
| 2026-05-09 | [Frontend Guidelines](active/FRONTEND_GUIDELINES.md) | active — dual extraction scope |
| 2026-05-09 | [Backend Structure](active/BACKEND_STRUCTURE.md) | active — dual extraction scope |
| 2026-05-09 | [Implementation Plan](active/IMPLEMENTATION_PLAN.md) | active — dual extraction scope |

## Planned Work

| date | title | status/PR |
|---|---|---|
| 2026-05-12 | [parse document module refactor](planned/2026-05-12-parse-document-refactor.md) | planned |

## Active Code Reviews

| date | title | status/PR |
|---|---|---|
| 2026-05-12 | [cross-lingual module](codereview/2026-05-12-feat-cross-lingual-module.md) | changes requested |

## Archive Index

### Completed Plans

| date | title | status/PR |
|---|---|---|
| 2026-05-11 | [translation & formatting module](archive/plans/2026-05-11-translation-formatting-module.md) | implemented — branch `feat/cross-lingual-module-v2` |
| 2026-05-12 | [MinerU2.5-Pro vllm local deployment](archive/plans/2026-05-12-mineru-vllm-local-deployment.md) | completed |
| 2026-05-11 | [net-io MinerU local upload](archive/plans/2026-05-11-net-io-mineru-local-upload.md) | completed |
| 2026-05-11 | [parse-document integration test (MinerU + PaddleOCR)](archive/plans/2026-05-11-parse-document-integration-test.md) | completed |
| 2026-05-11 | [MinerU VLM + vllm migration](archive/plans/2026-05-11-mineru-vlm-vllm-migration.md) | completed |
| 2026-05-09 | [parse-document module](archive/plans/2026-05-09-parse-document-module.md) | completed |
| 2026-05-09 | [rename literature-io to http-io + MinerU](archive/plans/2026-05-09-rename-literature-io-to-http-io-and-add-mineru.md) | merged |
| 2026-05-08 | [rust-io facade refactor](archive/plans/2026-05-08-rust-io-facade-refactor.md) | merged |
| 2026-05-07 | [files-io module](archive/plans/2026-05-07-files-io-module.md) | completed |
| 2026-05-07 | [selectolax migration](archive/plans/2026-05-07-selectolax-migration.md) | completed |
| 2026-05-07 | [user upload](archive/plans/2026-05-07-user-upload.md) | completed |
| 2026-05-06 | [literature acquisition](archive/plans/2026-05-06-literature-acquisition.md) | completed |
| 2026-05-05 | [rust-io literature gateway](archive/plans/2026-05-05-rust-io-literature-gateway.md) | completed |

### Completed Code Reviews

| date | title | status/PR |
|---|---|---|
| 2026-05-12 | [cross-lingual module v2 — fixes applied](archive/codereview/2026-05-12-feat-cross-lingual-module.md) | resolved |
| 2026-05-11 | [mineru-vlm-vllm review pass 4 — approved](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-4.md) | approved |
| 2026-05-11 | [mineru-vlm-vllm review pass 3](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-3.md) | resolved |
| 2026-05-11 | [mineru-vlm-vllm review pass 2](archive/codereview/2026-05-11-mineru-vlm-vllm-migration-review-2.md) | resolved |
| 2026-05-09 | [rename-literature-io pass 4](archive/codereview/rename-literature-io-to-http-io-2026-05-09.md) | approved |
| 2026-05-08 | [rust-io facade pass 7](archive/codereview/rust-io-facade-2026-05-08-pass7.md) | approved |
| 2026-05-08 | [rust-io facade pass 6](archive/codereview/rust-io-facade-2026-05-08-pass6.md) | approved |
| 2026-05-08 | [rust-io facade pass 5](archive/codereview/rust-io-facade-2026-05-08-pass5.md) | approved |
| 2026-05-08 | [rust-io facade pass 4](archive/codereview/rust-io-facade-2026-05-08-pass4.md) | approved |
| 2026-05-08 | [rust-io facade pass 3](archive/codereview/rust-io-facade-2026-05-08-pass3.md) | approved |
| 2026-05-08 | [rust-io facade](archive/codereview/rust-io-facade-2026-05-08.md) | approved |
| 2026-05-08 | [files-io final](archive/codereview/files-io-2026-05-08-final.md) | approved |
| 2026-05-08 | [files-io second](archive/codereview/files-io-2026-05-08-second.md) | approved |
| 2026-05-08 | [files-io](archive/codereview/files-io-2026-05-08.md) | approved |
| 2026-05-08 | [rust-io facade review v2](archive/codereview/code_review_rust_io_facade_v2.md) | archived |
| 2026-05-08 | [rust-io facade review](archive/codereview/code_review_rust_io_facade.md) | archived |
