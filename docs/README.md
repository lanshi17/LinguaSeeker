# Documentation Index

## Directory Structure

```
docs/
├── README.md          # This file — index & classification rules
├── archive/           # Completed work (plans + code reviews)
│   ├── plans/
│   └── codereview/
├── active/            # Currently in progress
├── planned/           # Not started yet
├── codereview/        # Active code reviews (in progress)
└── templates/         # Document templates
    ├── plan.md
    └── codereview.md
```

## Classification Rules

### Status Lifecycle

Every document goes through these stages:

```
planned/ → active/ → archive/
```

### When to Move Documents

| From | To | Trigger |
|---|---|---|
| `planned/` | `active/` | Implementation started (first commit) |
| `active/` | `archive/` | PR merged to `dev` branch |
| `codereview/` | `archive/codereview/` | Review approved + PR merged |

### Naming Convention

```
YYYY-MM-DD-<kebab-case-description>.md
```

Examples:
- `2026-05-07-files-io-module.md`
- `2026-05-08-selectolax-migration.md`

### Document Headers

Every plan must include in its header:
- **Status:** planned | in-progress | completed
- **Created:** date
- **Completed:** date (when done)
- **PR:** link/number (when merged)

### Code Review Documents

- Active reviews go in `codereview/`
- Completed reviews go in `archive/codereview/`
- Naming: `<module>-YYYY-MM-DD.md` (add `-second`, `-final` for multiple rounds)

### Orphan Cleanup

- Documents older than 30 days with status "planned" should be reviewed — either start or close them
- Code reviews with "changes-requested" older than 14 days should be pinged

---

## Active Plans

| Date | Plan | Status |
|---|---|---|
| — | (none) | — |

## Planned (Not Started)

| Date | Plan | Location |
|---|---|---|
| 2026-05-08 | [Rust I/O Facade Refactor](../backend/docs/planned/2026-05-08-rust-io-facade-refactor.md) | backend/docs/planned/ |

---

## Archive Index

### Completed Plans

| Date | Plan | PR |
|---|---|---|
| 2026-05-05 | [Rust I/O Literature Gateway](archive/plans/2026-05-05-rust-io-literature-gateway.md) | merged |
| 2026-05-06 | [Literature Acquisition Module](archive/plans/2026-05-06-literature-acquisition.md) | merged |
| 2026-05-07 | [Files I/O Module](archive/plans/2026-05-07-files-io-module.md) | merged |
| 2026-05-07 | [Selectolax Migration](archive/plans/2026-05-07-selectolax-migration.md) | merged |
| 2026-05-07 | [User Upload](archive/plans/2026-05-07-user-upload.md) | merged |

### Completed Code Reviews

| Date | Module | Rounds |
|---|---|---|
| 2026-05-08 | files-io | 3 (initial, second, final) |
