# Archived: GIM model-panel diagnostic packet concept

**Status:** completed / superseded
**Created:** 2026-08-28
**Archived:** 2026-09-01

This document formerly described an LLM voting panel as the case-level
reference standard for the GIM three-arm study. It is archived because that
design is incompatible with the formal scorer contract and with the
review-required study boundary.

The current prospective protocol uses two independent qualified
clinical-genetics reviewers and a third qualified clinical-genetics
adjudicator for discordant decisions. An LLM panel may be retained only as an
engineering diagnostic. It must not supply a reference standard, formal
reviewer packet, gold material, score input, clinical conclusion, or
submission result.

The historical diagnostic JSON remains in
`docs/gim/supplementary/reports/model_panel_report_20260828.json`. Its input
digest does not match the current frozen direct-inference input, so it is not
reusable without restoring its exact input snapshot or producing a newly
versioned diagnostic artifact. Neither option advances `ready=0`.
