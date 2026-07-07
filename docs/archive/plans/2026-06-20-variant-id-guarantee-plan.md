# Variant ID Guarantee — Fix Unknown Variant IDs in Evidence DB

**Status:** completed
**Created:** 2026-06-20
**Completed:** 2026-06-20
**PR:** merged

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Guarantee every variant-scoped evidence record carries a resolvable, stable `variant_id` (ClinVar `external_id` preferred; deterministic internal fallback otherwise), and propagate it end-to-end through `normalized_entities` → `canonical_evidence_items.active_payload` → `frontend_search_index.variant_ids`.

**Architecture:** Layered fix. (1) Widen ClinVar alias indexing so the precise matcher hits more variants. (2) Unify stop-codon normalization between importer and query sides. (3) Strengthen gene-context disambiguation so multi-hit variants resolve instead of collapsing to `ambiguous`. (4) Add a deterministic internal `variant_id` synthesis as the guarantee layer — every variant entity gets an `external_id`, never NULL. (5) Wire `variant_id` into the canonical evidence payload and the search-index refresh. (6) Backfill existing data and verify.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, PostgreSQL 16 + pgvector, pytest + pytest-asyncio, Ruff (Google style, line 120). All commands via `uv`.

---

## Background — Why Unknown Variant IDs Exist

The evidence DB uses `variant_id` (the `normalized_entities.external_id` for `entity_type='variant'`) as the primary pivot dimension. Current state in `lingua_dev`:

| status | count | external_id |
|---|---|---|
| standardized | 3 | ClinVar ID present |
| ambiguous | 4 | NULL |
| unmapped | 20 | NULL |

Plus `frontend_search_index.variant_ids` is `[]` for all 2349 rows — the variant dimension is never populated.

### Four root causes (all code- and data-verified)

**RC1 — ClinVar alias indexing too narrow.** `importers.py:459-516` indexes only 3 alias types per ClinVar variant: full `name`, derived `protein_short` (one-letter), and `rsid`. It does NOT index the bare `c.` form extracted from the full name. So literature text `c.4748T>G` → 0 alias hits → `unmapped`, even though `ClinVarVariation:4468` is the correct entry (its full name is `NM_177438.3(DICER1):c.4748T>G (p.Leu1583Arg)`). Verified: `c.4748T>G`, `c.196G>A`, `c.290A>G` have 0 rows in `terminology_aliases`.

**RC2 — Stop-codon mapping asymmetry.** Importer maps `Ter → "X"` (`importers.py:60` `AA3_TO_1["Ter"]="X"`), producing indexed aliases like `p.R243X`. Query-side `hgvs_normalizer._convert_protein_3letter` maps `Ter|* → "*"` (`hgvs_normalizer.py:50`), producing lookup aliases like `p.R243*`. DB proof: `p.R243X`=18 rows, `p.R243*`=0 rows. Literature `p.Arg243*` → normalizes to `p.R243*` → no match → `unmapped`. `p.Arg75stop` is worse: `stop` matches neither `[A-Z][a-z]{2}` nor `Ter` nor `*`, so no alias is derived at all.

**RC3 — Gene-context disambiguation collapses to ambiguous.** `precise_match/core.py:137-153` `_filter_variant_candidates_by_gene_context` compares `candidate.metadata['gene_symbol']` (raw literature text from `adapters.py:143` `chain.gene_text`) against `TerminologyCandidate.raw_payload['gene_symbol']` (ClinVar `GeneSymbol` column) via **raw string equality**. On mismatch it does `return filtered or choices` — falling back to the full candidate set, which triggers `ambiguous`. `p.A168T` spans 95 ClinVar genes; any gene-symbol casing/alias mismatch → ambiguous.

**RC4 — variant_id never propagated.** No code path writes `variant_ids` (or `gene_ids`/`entity_ids`/`search_text`) into `canonical_evidence_items.active_payload`. `search_index_repo.refresh()` reads them via `COALESCE(active_payload->'variant_ids','[]')` but the payload key is always absent → `[]`. `upsert_canonical_evidence` (`repositories.py:944-948`) only sets `track` and `entity_id` (the normalized-entity UUID), never a ClinVar `external_id` or a `variant_ids` array.

### Requirement

> 我们是以变异 id 为主维度的，必须存在。

Every variant entity MUST have a non-NULL `external_id`. ClinVar match → `ClinVarVariation:<id>`. No ClinVar match → deterministic synthetic internal id `internal:variant:<sha8>`. The `unmapped` status is retained for audit, but `external_id` is never NULL for variants.

---

## Design Decisions

**D1 — Single source of truth for stop-codon mapping.** Introduce `STOP_CODON_ONE_LETTER = "*"` in `importers.py` and use it in both `_derive_hgvs_protein_alias` and `hgvs_normalizer._convert_protein_3letter`. Map `Ter`/`*`/`stop`/`X`→`*` on the query side; reindex ClinVar so existing `X` aliases become `*`. (We keep `X`→`*` migration in the reindex, not at query time, to keep the query normalizer pure.)

**D2 — Widen ClinVar alias indexing.** Extract bare `c.` notation from the ClinVar full name (strip `NM_xxx(GENE):` transcript prefix, strip trailing ` (p....)` protein suffix) and index it as alias_type `coding`. Also index `del`/`dup`/`fs`/`ins` protein forms that `_derive_hgvs_protein_alias` currently skips — extend the regex to capture `fs`/`del`/`dup`/`ins` alt tokens and map them through.

**D3 — Gene-context disambiguation with normalized fallback.** Normalize both sides with `normalize_gene_symbol` before comparison. If the normalized comparison still yields ≥2 distinct genes but the candidate gene is unmapped itself, keep the highest-evidence candidate (alias_type priority) rather than the full set — i.e. pick a winner by alias-type priority then gene match, not "all or nothing". Only return `ambiguous` when ≥2 candidates share the SAME normalized gene AND same alias-type priority.

**D4 — Deterministic internal variant_id guarantee.** New helper `make_internal_variant_id(normalized_hgvs, gene_symbol) -> str` returning `internal:variant:<sha8(normalized|gene)>`. In `upsert_normalized_entity`, when `entity_type==VARIANT` and `match.status != STANDARDIZED`, set `external_id = make_internal_variant_id(...)` and `standardization_status` stays `unmapped` (audit) but `external_id` is non-NULL. Add a partial unique index `uq_normalized_entities_variant_internal_id` on `(external_id)` where `external_id LIKE 'internal:variant:%'`.

**D5 — Propagate variant_id into canonical evidence + search index.** In `upsert_canonical_evidence`, fetch the variant entity's `external_id` (via `entity_ids_by_candidate_id` → `NormalizedEntity`) and write `variant_id` + `variant_ids: [external_id]` and `gene_ids` into `active_payload`. `search_index_repo.refresh()` already reads these keys — no SQL change needed once the payload is populated.

**D6 — Backfill, not migrate.** Existing `normalized_entities`/`canonical_evidence_items` rows are backfilled in-place by a one-shot script (`scripts/backfill_variant_ids.py`) rather than an Alembic data migration, because the logic lives in Python helpers. A schema migration only adds the new partial unique index.

---

## Conventions

- All Python via `uv run pytest ...` / `uv run ruff check`.
- Tests under `backend/tests/core/standardize_entities_and_align_knowledge/` mirror source structure.
- TDD: write failing test → verify fail → implement → verify pass → commit.
- Commit messages: Conventional Commits, English.
- No `-> dict` returns (AGENTS.md §22). No裸 dict contracts.
- Worktree: medium task → create isolated worktree on `dev` (AGENTS.md §13).

---

## Phase 1 — Stop-Codon Normalization Unification (RC2)

### Task 1.1: Add shared stop-codon constant and query-side mapping

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/importers.py` (add constant, use in `AA3_TO_1`/`_derive_hgvs_protein_alias`)
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/hgvs_normalizer.py:50` (map `X`→`*` too)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`

**Step 1: Write failing tests**

In `test_hgvs_normalizer.py`:
```python
def test_stop_codon_x_alias_maps_to_star() -> None:
    """Literature `p.R243X` (X stop) normalizes to the `*` form for lookup."""
    assert "p.R243*" in expand_hgvs_aliases("p.R243X")


def test_stop_word_alt_derives_star_alias() -> None:
    """`p.Arg75stop` derives the `p.R75*` one-letter alias."""
    aliases = expand_hgvs_aliases("p.Arg75stop")
    assert "p.R75*" in aliases
```

In `test_importers.py`, add a test asserting `_derive_hgvs_protein_alias("...p.Arg243Ter")` returns `p.R243*` (not `p.R243X`).

**Step 2: Run — verify fail**

`uv run pytest backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py::test_stop_codon_x_alias_maps_to_star backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py -v`
Expected: FAIL (X not mapped; `stop` not recognized).

**Step 3: Implement**

- `importers.py`: change `AA3_TO_1["Ter"] = "X"` → `"*"`. Add module constant `STOP_ALT_TOKENS = {"Ter", "*", "stop", "X"}`.
- Extend `HGVS_PROTEIN_3LETTER_RE` alt group: `([A-Z][a-z]{2}|Ter|\*|stop|X)`. In `_derive_hgvs_protein_alias`, map alt via `STOP_CODON_ONE_LETTER = "*"` when alt in `STOP_ALT_TOKENS`.
- `hgvs_normalizer.py:50`: `alt1 = "*" if alt3 in ("Ter", "*", "stop", "X") else AA3_TO_1.get(alt3)`. Update `_PROTEIN_3LETTER_RE` alt group identically.

**Step 4: Run — verify pass**

`uv run pytest backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_normalizer.py backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py -v`
Expected: PASS. Also run full normalizer/importer suite to catch regressions.

**Step 5: Commit**

`git commit -m "fix(standardize): unify stop-codon mapping to '*' across importer and normalizer"`

---

## Phase 2 — Widen ClinVar Alias Indexing (RC1)

### Task 2.1: Extract and index bare `c.` coding aliases

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/importers.py` (`iter_clinvar_batches`, ~line 459-516)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`

**Step 1: Write failing test**

```python
def test_clinvar_bare_coding_alias_indexed() -> None:
    """A ClinVar name with transcript prefix yields a bare c. alias."""
    batch = next(iter_clinvar_batches_from_rows([{
        "VariationID": "4468",
        "Name": "NM_177438.3(DICER1):c.4748T>G (p.Leu1583Arg)",
        "ReviewStatus": "criteria provided, single submitter",
        "ClinicalSignificance": "Pathogenic",
        "GeneSymbol": "DICER1",
        "RS# (dbSNP)": "rs137852976",
    }], version="test"))
    alias_texts = {a.alias_text for a in batch.aliases}
    assert "c.4748T>G" in alias_texts
    assert any(a.alias_type == "coding" for a in batch.aliases if a.alias_text == "c.4748T>G")
```

(If `iter_clinvar_batches_from_rows` test helper does not exist, add a thin wrapper in the test module that builds one row dict and calls the same parsing path.)

**Step 2: Run — verify fail**

Expected: FAIL — `c.4748T>G` not in aliases.

**Step 3: Implement**

Add `_extract_bare_coding_alias(name: str) -> str | None`:
- Strip `^(NM|NR|XM|XR|NG)_[\d.]+(\([^)]+\))?:` transcript prefix (reuse `_TRANSCRIPT_PREFIX_RE` from `hgvs_normalizer` — import it).
- Take the first whitespace-delimited token; if it starts with `c.` return its `normalize_variant_text`, else return `None`.
- Drop any trailing ` (p....)` — the bare coding form is everything before the first ` (`.

In `iter_clinvar_batches`, after computing `protein_alias`, compute `coding_alias = _extract_bare_coding_alias(name)`. If present, append to `alias_values` and emit an `ImportAlias(alias_type="coding", ...)`.

**Step 4: Run — verify pass**

Expected: PASS. Run `test_importers.py` fully.

**Step 5: Commit**

`git commit -m "feat(standardize): index bare c. coding aliases for ClinVar variants"`

### Task 2.2: Index `fs`/`del`/`dup`/`ins` protein forms

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/importers.py` (`_derive_hgvs_protein_alias`, `HGVS_PROTEIN_3LETTER_RE`)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`

**Step 1: Write failing test**

```python
def test_protein_fs_alias_derived() -> None:
    assert _derive_hgvs_protein_alias("NM_000245.3(MEN1):c.3927_3931del (p.Glu1309fs)") == "p.E1309fs"


def test_protein_del_alias_derived() -> None:
    assert _derive_hgvs_protein_alias("...p.Phe508del") == "p.F508del"
```

**Step 2: Run — verify fail** — current regex requires a 3-letter alt, `fs`/`del` not captured.

**Step 3: Implement**

Extend `HGVS_PROTEIN_3LETTER_RE` alt group to `([A-Z][a-z]{2}|Ter|\*|stop|X|fs|del|dup|ins)`. In `_derive_hgvs_protein_alias`, when alt token is `fs`/`del`/`dup`/`ins`, emit it verbatim (no AA3_TO_1 lookup): `f"{prefix}{ref1}{pos}{alt_token}"`.

**Step 4: Run — verify pass**

**Step 5: Commit**

`git commit -m "feat(standardize): derive fs/del/dup/ins protein aliases from ClinVar names"`

---

## Phase 3 — Gene-Context Disambiguation (RC3)

### Task 3.1: Normalize gene symbols before comparison

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/precise_match/core.py:137-153`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py`

**Step 1: Write failing test**

Construct a scenario: candidate gene `BRCA1` (metadata), ClinVar candidates from genes `BRCA1` (2 entries, alias_type `protein_short`) and `BRCA2` (1 entry, `protein_short`). Assert the matcher returns `STANDARDIZED` with the BRCA1 entry, not `AMBIGUOUS`.

Also test: candidate gene `brca1` (lowercase literature) vs ClinVar `BRCA1` → still resolves (normalized equality).

**Step 2: Run — verify fail** — current raw-equality path returns the full set → ambiguous.

**Step 3: Implement**

In `_filter_variant_candidates_by_gene_context`:
- Normalize candidate gene: `norm_gene = normalize_gene_symbol(gene_symbol)`.
- For each choice, normalize `choice.raw_payload['gene_symbol']` the same way.
- Partition: `same_gene = [c for c in choices if norm_choice == norm_gene]`.
- If `same_gene`: apply `_apply_alias_type_priority(same_gene)`; if the result is a single entry → return it; if still multiple with same alias-type priority AND same normalized gene → these are genuinely the same variant reported by multiple submitters → return the first (deterministic) rather than ambiguous. (Rationale: ClinVar duplicates the same variant across transcripts; same gene + same protein alias = same variant.)
- If `not same_gene`: do NOT fall back to all choices. Instead return the highest alias-type-priority choice across ALL choices (gene-agnostic best), so a winner always exists. Only set ambiguous when ≥2 choices tie on BOTH normalized gene AND alias-type priority.

This requires `_finalize` to receive the pre-filtered set; ensure `_match_variant` calls the filter before `_finalize`.

**Step 4: Run — verify pass** + full `test_precise_match.py`.

**Step 5: Commit**

`git commit -m "fix(standardize): normalize gene context and avoid ambiguous collapse for variants"`

---

## Phase 4 — Variant ID Guarantee Layer (RC4 core)

### Task 4.1: `make_internal_variant_id` helper

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/variant_id.py`
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_variant_id.py`

**Step 1: Write failing test**

```python
def test_internal_variant_id_stable_and_prefixed() -> None:
    from src.core.standardize_entities_and_align_knowledge.variant_id import make_internal_variant_id
    vid = make_internal_variant_id("c.4748T>G", "DICER1")
    assert vid.startswith("internal:variant:")
    assert vid == make_internal_variant_id("c.4748T>G", "DICER1")
    assert vid != make_internal_variant_id("c.4748T>G", "BRCA1")


def test_internal_variant_id_normalizes_input() -> None:
    from src.core.standardize_entities_and_align_knowledge.variant_id import make_internal_variant_id
    assert make_internal_variant_id(" c.4748T>G ", "dicer1") == make_internal_variant_id("c.4748T>G", "DICER1")
```

**Step 2: Run — verify fail** (module missing).

**Step 3: Implement**

```python
"""Deterministic internal variant identifiers for unmatched variants."""
from __future__ import annotations
import hashlib
from src.core.standardize_entities_and_align_knowledge.normalizers import normalize_gene_symbol, normalize_variant_text

_PREFIX = "internal:variant:"

def make_internal_variant_id(normalized_hgvs: str, gene_symbol: str) -> str:
    """Return a stable internal id for a variant with no ClinVar match."""
    gene = normalize_gene_symbol(gene_symbol) if gene_symbol else "_"
    hgvs = normalize_variant_text(normalized_hgvs)
    digest = hashlib.sha256(f"{gene}|{hgvs}".encode("utf-8")).hexdigest()[:8]
    return f"{_PREFIX}{digest}"
```

**Step 4: Run — verify pass**

**Step 5: Commit**

`git commit -m "feat(standardize): add deterministic internal variant id helper"`

### Task 4.2: Guarantee non-NULL external_id for variant entities

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py:749-793` (`upsert_normalized_entity`)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing test**

Async test: persist an `UNMAPPED` variant match with `raw_text="c.4748T>G"`, `metadata={"gene_symbol":"DICER1"}`. Assert the resulting `NormalizedEntity.external_id` starts with `internal:variant:` and `standardization_status == "unmapped"`. Assert a second identical insert returns the SAME entity_id (idempotent via the internal id).

**Step 2: Run — verify fail** — current code sets `external_id=None` for non-standardized.

**Step 3: Implement**

In `upsert_normalized_entity`, after computing `normalized_raw_text`:
```python
external_id = match.external_id
if (match.candidate.entity_type == EntityType.VARIANT
        and match.status != MatchStatus.STANDARDIZED
        and not external_id):
    gene = str(match.candidate.metadata.get("gene_symbol", "") or "").strip()
    external_id = make_internal_variant_id(match.candidate.raw_text, gene)
```
Use `external_id` when constructing `NormalizedEntity` (replace the `match.external_id if status==STANDARDIZED else None` ternary). Update the lookup query for the unmapped path to match on `external_id == internal_id` so repeated inserts are idempotent (currently it matches on `normalized_raw_text` + status — keep that as a secondary match, but prefer `external_id` match first to avoid duplicates across gene contexts).

**Step 4: Run — verify pass** + `test_repositories.py` full.

**Step 5: Commit**

`git commit -m "feat(standardize): guarantee non-NULL variant external_id via internal fallback"`

### Task 4.3: Schema migration — partial unique index on internal variant ids

**Files:**
- Create: Alembic migration `backend/...migrations/versions/<rev>_add_variant_internal_id_index.py` (locate the alembic env first via `find`)
- Test: `backend/tests/dao/postgresql/test_alembic_migration.py` (add assertion)

**Step 1: Write failing test** — assert the migration creates index `uq_normalized_entities_variant_internal_id` with predicate `external_id LIKE 'internal:variant:%'`.

**Step 2: Run — verify fail.**

**Step 3: Implement** migration: `op.execute("CREATE UNIQUE INDEX ... ON normalized_entities (external_id) WHERE external_id LIKE 'internal:variant:%'")` (up) / `DROP INDEX` (down). Downgrade must drop before any data backfill.

**Step 4: Run — verify pass.**

**Step 5: Commit**

`git commit -m "feat(dao): add partial unique index for internal variant ids"`

---

## Phase 5 — Propagate variant_id into Canonical Evidence & Search Index (RC4)

### Task 5.1: Write variant_id / variant_ids / gene_ids into active_payload

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py:897-987` (`upsert_canonical_evidence`)
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing test**

Assert that after `upsert_canonical_evidence`, a variant-field canonical row's `active_payload` contains:
- `variant_id`: the entity's `external_id` (ClinVar or `internal:variant:...`)
- `variant_ids`: `[external_id]`
- `gene_ids`: `[gene_external_id]` when a gene binding exists

**Step 2: Run — verify fail.**

**Step 3: Implement**

In `upsert_canonical_evidence`, we already have `entity_ids_by_candidate_id`. Add a pre-pass: for each candidate, load the `NormalizedEntity` (batch) to get `external_id` and `entity_type`. Build `entity_external_ids_by_candidate_id: dict[str, tuple[str,str]]` (external_id, entity_type). Then when constructing `payload`:
```python
variant_ids = [eid for (eid, etype) in entity_externals if etype == EntityType.VARIANT.value]
gene_ids = [eid for (eid, etype) in entity_externals if etype == EntityType.GENE.value]
payload = {
    **row.raw_payload,
    "track": row.track,
    "entity_id": entity_ids_by_candidate_id.get(spec.candidate_id),
    "variant_id": variant_ids[0] if variant_ids else None,
    "variant_ids": variant_ids,
    "gene_ids": gene_ids,
    "entity_ids": [eid for (eid, _) in entity_externals],
    "search_text": _build_search_text(row, entity_externals),
}
```
Add `_build_search_text` concatenating field value + gene/variant/disease display names for the `search_text` payload key (currently also never populated).

Because `upsert_canonical_evidence` runs per-run, batch the entity lookups to avoid N+1 (reuse the `_BATCH_SIZE` pattern).

**Step 4: Run — verify pass** + full repo tests.

**Step 5: Commit**

`git commit -m "feat(standardize): populate variant_id/variant_ids/gene_ids in canonical evidence payload"`

### Task 5.2: Verify search index refresh picks up variant_ids (no SQL change)

**Files:**
- Test: `backend/tests/dao/postgresql/test_search_index_repo.py`

**Step 1: Write test** — insert a canonical evidence item with `active_payload` containing `variant_ids: ["ClinVarVariation:4468"]`, call `refresh()`, assert `frontend_search_index.variant_ids` for that row equals `["ClinVarVariation:4468"]` and that `search(variant_ids=["ClinVarVariation:4468"])` returns it.

**Step 2: Run — verify pass** (the refresh SQL already COALESCEs the key; this test pins the contract).

**Step 3: Commit**

`git commit -m "test(dao): pin search index variant_ids propagation contract"`

---

## Phase 6 — Reindex & Backfill Existing Data

### Task 6.1: Reindex ClinVar terminology with widened aliases

**Files:**
- Modify: the ClinVar import entrypoint (locate via `codegraph_search` for `parse_clinvar_rows` callers / `scripts/import_terminology.py`)
- Create: `scripts/reindex_clinvar_aliases.py`

**Step 1: Implement reindex script**

Re-run ClinVar import (upsert path is idempotent on `external_id`). The new aliases (`coding`, `fs`/`del` forms, `*` stop form) are inserted; old `X` aliases remain but are now dead (harmless) — optionally clean them: `DELETE FROM terminology_aliases WHERE entity_type='variant' AND normalized_alias ~ 'p\.[A-Z]\d+X$'` after reindex (the `*` form supersedes them). Document this in the script.

**Step 2: Run reindex** against the dev ClinVar TSV. Verify counts: `terminology_aliases` where `entity_type='variant'` and `alias_type='coding'` > 0; `p.R243*` now present.

**Step 3: Commit**

`git commit -m "feat(standardize): reindex ClinVar aliases with coding and stop forms"`

### Task 6.2: Backfill variant_id on existing normalized_entities + canonical evidence

**Files:**
- Create: `scripts/backfill_variant_ids.py`

**Step 1: Implement**

1. For every `normalized_entities` row where `entity_type='variant'` and `external_id IS NULL`: compute `make_internal_variant_id(normalized_raw_text, raw_payload->>'gene_symbol' or aliases[0])`, set `external_id`, commit in batches of 1000. Respect the new partial unique index (dedup by internal id; merge duplicates via `merged_into_entity_id`).
2. For every `canonical_evidence_items` row whose `field_id` is variant-scoped (in `_VARIANT_FIELDS` from extract_evidence contracts) or whose `active_payload->>'entity_id'` points to a variant entity: reload the entity `external_id`, set `active_payload` `variant_id`/`variant_ids`/`gene_ids`/`entity_ids`/`search_text` as in Task 5.1.
3. Call `SearchIndexRepository.refresh()` to rebuild `frontend_search_index`.

**Step 2: Run backfill** against `lingua_dev`. Verify:
- `SELECT COUNT(*) FROM normalized_entities WHERE entity_type='variant' AND external_id IS NULL` → 0.
- `SELECT COUNT(*) FROM canonical_evidence_items WHERE active_payload->>'variant_id' IS NULL AND <variant-scoped>` → 0.
- `SELECT COUNT(*) FROM frontend_search_index WHERE variant_ids != '[]'` → > 0.

**Step 3: Commit**

`git commit -m "feat(standardize): backfill variant_id across normalized entities and canonical evidence"`

---

## Phase 7 — End-to-End Verification

### Task 7.1: Regression — previously unmapped variants now resolve

**Files:**
- Test: `backend/tests/core/standardize_entities_and_align_knowledge/test_hgvs_integration.py`

**Step 1: Write parametrized test** covering the 24 previously-failing cases from the DB audit:
- `c.4748T>G` → `ClinVarVariation:4468` (coding alias)
- `p.Arg243*` / `p.Arg75stop` / `p.Trp159Ter` → their ClinVar entries (stop unification)
- `p.A168T` with gene `DRD4` → resolves to DRD4 entry (gene disambiguation), not ambiguous
- `p.Phe508del` / `p.Glu1309fs` → derived aliases (fs/del)
- A genuinely novel variant → `internal:variant:...` external_id, status unmapped

**Step 2: Run — verify pass.**

**Step 3: Commit**

`git commit -m "test(standardize): regression for previously unmapped variant forms"`

### Task 7.2: Pipeline E2E — variant_id present on every variant evidence

**Files:**
- Test: `backend/tests/integration/test_literature_profile_e2e.py` (extend) or new `test_variant_id_e2e.py`

Run a Phase 3 standardization over a fixture document; assert every variant-scoped canonical evidence row has a non-null `variant_id` in `active_payload`, and `frontend_search_index` returns rows when filtering by that `variant_id`.

### Task 7.3: Full suite + lint

`uv run ruff check` and `uv run pytest backend/tests/core/standardize_entities_and_align_knowledge backend/tests/dao/postgresql backend/tests/integration -v`. Fix any regressions.

### Task 7.4: Record progress + lesson

- Append to `progress.txt`: `[2026-06-20] [Variant ID guarantee fix] [completed]`
- Append to `lesson.md`: root-cause summary (4 RCs), the stop-codon asymmetry lesson, and the "never NULL external_id for primary dimension" preventive measure.

---

## Risk & Rollback

- **Risk:** Gene-disambiguation change (D3) may now pick a wrong winner when the literature gene is itself wrong. **Mitigation:** keep `ambiguous` for the genuine same-gene-same-priority tie; the winner-pick only applies when candidate gene is absent or unmatched — log a `rationale` noting gene-agnostic resolution for audit.
- **Risk:** Backfill merging duplicates by internal id could lose audit history. **Mitigation:** use `merged_into_entity_id` + `EntityMergeEvent` rows, never hard-delete.
- **Rollback:** Each phase is independently revertible via `git revert`. The schema migration (4.3) has a clean down. The backfill is idempotent and additive (only sets previously-NULL `external_id` and adds payload keys).

---

## Out of Scope

- Re-running Phase 2 extraction on existing documents (only Phase 3 re-standardization + reindex).
- Frontend UI changes to surface `variant_id` (the search index already supports `variant_ids` filtering; frontend wiring is a separate task).
- ClinVar TSV version upgrade.
