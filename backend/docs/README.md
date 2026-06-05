# Documentation Index

## Directory Structure

```
docs/
├── README.md          # This file — index & classification rules
├── archive/           # Completed work
│   ├── plans/         # Finished implementation plans
│   └── codereview/    # Completed code reviews
├── active/            # Currently in progress
├── planned/           # Not started yet
├── codereview/        # Active code reviews
└── templates/         # Document templates (plan.md, codereview.md)
```

## Classification Rules

| Status | Location |
|---|---|
| `planned` | `planned/` |
| `in-progress` | `active/` |
| `completed` | `archive/plans/` or `archive/codereview/` |
| Active review | `codereview/` |

Status is detected from the document's `**Status:**` field, cross-referenced with git history and source code.

## Naming Convention

```
YYYY-MM-DD-<kebab-case-description>.md
```

## Active Plans

| Date | Document | Status |
|---|---|---|

## Planned

| Date | Document | Status |
|---|---|---|

## Archive

| Date | Document | Type |
|---|---|---|
