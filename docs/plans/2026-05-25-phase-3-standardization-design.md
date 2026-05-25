# Phase 3 Entity Standardization Design

**Status:** planned
**Created:** 2026-05-25
**Completed:** —
**PR:** —

## Goal

Implement the Phase 3 MVP for deterministic biomedical entity standardization and knowledge alignment: import local terminology resources, match extracted evidence entities to public database identifiers, persist standardized bindings, and update canonical evidence records.

## Approved Scope

In scope:

- Use `DualEvidenceExtractionResult` as the MVP input path.
- Keep a future `FusedResultAdapter` contract boundary, but do not implement fused input now.
- Import HGNC, OMIM, HPO, and ClinGen terminology data from `database/terminology_database/`.
- Import ClinVar from `database/terminology_database/clinvar/variant_summary.txt` only.
- Exclude ClinVar 0-star or evidence-free records; import 1-star and above records and preserve review status metadata.
- Match genes, diseases, phenotypes, and variants with deterministic exact and synonym rules.
- Write standardized and unresolved entities to `normalized_entities`.
- Write run-level evidence, entity bindings, and selected canonical evidence records.

Out of scope:

- dbSNP full import, including `GCF_000001405.40.gz`.
- pgvector or embedding semantic retrieval.
- Agent or LLM-based conflict disambiguation.
- gnomAD population frequency lookup.
- Human review queue UI.
- Full MONDO import.

## Architecture

Phase 3 is a vertical feature slice under:

```text
backend/src/core/standardize_entities_and_align_knowledge/
```

The slice exposes an orchestrator-facing service in `api.py`, keeps deterministic business rules in `core.py`, wraps SQLAlchemy persistence in `repositories.py`, stores typed contracts in `contracts.py`, and keeps normalization/hash behavior in `normalizers.py`. The implementation must not place biomedical matching rules in `backend/src/agents/`; workflow code only wires the Phase 3 node.

The MVP input path is:

```text
DualEvidenceExtractionResult
  -> DualResultAdapter
  -> StandardizationInput
  -> StandardizationService
  -> TerminologyMatcher
  -> StandardizationRepository
  -> normalized_entities / run_evidence_items / evidence_entity_bindings / canonical_evidence_items
```

## Reference Tables

Use a unified terminology projection rather than source-specific tables.

### `terminology_entries`

One row per standard entity:

- `entry_id`: UUID primary key.
- `entity_type`: `gene`, `disease`, `phenotype`, or `variant`.
- `source_db`: `HGNC`, `OMIM`, `HPO`, `MONDO`, `ClinVar`, or another controlled source string.
- `external_id`: prefixed source identifier, for example `HGNC:1100`, `OMIM:232600`, `HP:0001250`, `MONDO:0013212`, `ClinVarVariation:12345`.
- `display_name`: source display name.
- `normalized_name`: deterministic normalized lookup key.
- `aliases`: JSONB payload snapshot of display aliases in original casing.
- `raw_payload`: source-specific fields needed for audit and future re-import.
- `version`: import batch tag such as `hgnc_20260525`; this is batch provenance, not optimistic locking.
- timestamps.

`terminology_entries.aliases` is display/audit payload. Matchers do not query it.

### `terminology_aliases`

One row per queryable alias:

- `alias_id`: UUID primary key.
- `entry_id`: FK to `terminology_entries`.
- `alias_text`: original alias text.
- `normalized_alias`: deterministic normalized lookup key.
- `alias_type`: `primary`, `alias`, `previous_symbol`, `rsid`, `hgvs`, `name`, or similar source-specific category.
- `source_db`.

Matchers query `terminology_aliases` only. `normalized_name` and `normalized_alias` must be produced by shared functions in `normalizers.py` so import-time and query-time normalization cannot drift.

### `terminology_relationships`

One row per structured reference relationship:

- `relationship_id`: UUID primary key.
- `subject_entry_id`: FK to `terminology_entries`.
- `object_entry_id`: nullable FK to `terminology_entries`.
- `relationship_type`: controlled relationship string.
- `source_db`.
- `evidence_level`: documented string value. No DB enum in MVP.
- `raw_payload`: source-specific relationship fields.

`object_entry_id` is nullable for relationships whose object is not a reference entity. For `variant_has_clinical_significance`, `subject_entry_id` points to the ClinVar variant entry, `object_entry_id` is `NULL`, and `raw_payload` stores `clinical_significance`, `review_status`, `review_stars`, `variation_id`, and supporting ClinVar fields.

MVP relationship types:

- `gene_associated_with_disease`
- `phenotype_associated_with_gene`
- `phenotype_associated_with_disease`
- `variant_associated_with_disease`
- `variant_has_clinical_significance`
- `gene_has_dosage_sensitivity`

Expected `evidence_level` values include ClinGen classifications (`definitive`, `strong`, `moderate`, `limited`, `disputed`, `refuted`, `no_known_disease_relationship`) and ClinVar review levels (`1_star`, `2_star`, `3_star`, `4_star`). Values are documented and normalized but not constrained by a DB enum.

## Terminology Import

The import command lives in `scripts/import_terminology.py` and delegates parsing and upsert logic to the Phase 3 package. Migrations only create schema; they do not parse TSV, CSV, JSON, OBO, or VCF-like data.

Import rules:

- HGNC: create `gene` entries from `hgnc_complete_set.txt`; aliases come from approved symbol, approved name, alias symbols, and previous symbols.
- OMIM: create `disease` entries from disease-bearing rows in `morbidmap.txt`, `genemap2.txt`, and `mimTitles.txt`; create gene-disease relationships when both sides can be resolved.
- HPO: create `phenotype` entries from `hp.json` or `hp.obo`; create phenotype-gene and phenotype-disease relationships from `phenotype_to_genes.txt`, `genes_to_phenotype.txt`, and `phenotype.hpoa`.
- ClinGen: create gene-disease relationships from `Clingen-Gene-Disease-Summary.csv`; create source-limited `MONDO:<id>` disease entries when the ClinGen disease is MONDO-only. Create dosage relationships from `Clingen-Dosage-Sensitivity.csv`.
- ClinVar: use `variant_summary.txt` as the source of truth. Create `variant` entries for imported rows. Query aliases include `rs<RS#>`, ClinVar `Name`, and parseable HGVS-like strings from `Name`.

ClinVar 0-star exclusion:

- Exclude `ReviewStatus` values that indicate no assertion basis or no classification, including `no assertion criteria provided`, `no classification provided`, `no classification for the single variant`, `no classifications from unflagged records`, `-`, and empty values.
- Import records with criteria provided, conflicting classifications, multiple submitters, expert panel, or practice guideline review statuses.
- Store the raw `ReviewStatus` and computed star level in `raw_payload`.

## Standardization Input

The core service consumes `StandardizationInput`, not Phase 2 contracts directly. MVP ships `DualResultAdapter`.

Candidate extraction:

- Gene, disease, and variant candidates come from `EvidenceChain.gene_text`, `EvidenceChain.disease_text`, and `EvidenceChain.variant_text`.
- Phenotype candidates come from phenotype-bearing `EvidenceItem` fields such as `B.hpo_terms`, `B.clinical_phenotypes`, `C.maternal_phenotype`, `C.paternal_phenotype`, `I.animal_model_phenotype`, and `I.cell_model_phenotype`.
- `DocumentEvidenceMap` is context metadata only.

When original and translated tracks contain the same chain/evidence field, the adapter selects the higher-confidence item for the current run-level value but preserves both track payloads and source spans in `raw_payload`.

## Matching Rules

Use deterministic matching only.

- Gene: HGNC exact approved symbol/name/alias/previous symbol. No edit distance.
- Disease: OMIM exact normalized name/alias first; HPO and source-limited MONDO are fallback candidates.
- Phenotype: HPO exact normalized name/alias.
- Variant: ClinVar exact `rsID`, `Name`, or HGVS-like alias. No fuzzy or vector match.

Match outcomes:

- Exactly one candidate: `standardized`.
- Multiple candidates: `ambiguous`.
- No candidate: `unmapped`.

`normalized_entities.external_id` always uses a source-prefixed string for standardized entities. Examples: `HGNC:1100`, `OMIM:232600`, `HP:0001250`, `MONDO:0013212`, `ClinVarVariation:12345`.

Unmapped and ambiguous entities are still inserted into `normalized_entities` with `external_id = NULL`, stable `normalized_raw_text`, and full match rationale in `raw_payload`. This gives later expert review or Agent resolution a durable `entity_id`.

## Persistence Rules

The caller supplies `source_document_id` and `processing_run_id`. Phase 3 does not create source documents or processing runs.

Write targets:

- `normalized_entities`: every standardized, unmapped, and ambiguous candidate.
- `run_evidence_items`: all FOUND and non-FOUND evidence items for complete run audit.
- `evidence_entity_bindings`: bindings from evidence to normalized entities.
- `canonical_evidence_items`: current-best evidence records for display/review.

Binding role mapping:

- `gene` -> `subject`
- `variant` -> `target`
- `disease` -> `context`
- `phenotype` -> `context`
- other future entity types -> `mention`

`entity_scope_hash` is computed at EvidenceChain granularity. All evidence items in the same chain share the same scope hash in MVP. The hash input is the sorted set of scope-bearing roles and entity identity strings for that chain.

Canonical creation/update:

- Create or update canonical rows for `FOUND`, `SOURCE_INVALID`, `OCR_GAP`, and `TABLE_UNGROUNDED`.
- Do not create canonical rows for ordinary `NOT_FOUND`.
- If a later run emits `NOT_FOUND` for a canonical key that previously had `FOUND`, keep the existing `FOUND` current best.
- Current-best status priority is `FOUND > SOURCE_INVALID > OCR_GAP > TABLE_UNGROUNDED > NOT_FOUND`.
- For equal status priority, higher confidence wins.
- If standardized entity IDs or status differ across runs for the same canonical key, set `conflict_flag = true`.

## Error Handling

Import errors are row-scoped where possible. Bad rows are counted and logged with source file, line number, and reason. Fatal errors are reserved for unreadable files, missing required columns, malformed migration state, or database write failures.

Standardization errors are candidate-scoped where possible. A candidate that cannot be matched becomes `unmapped` or `ambiguous`; it does not abort the document run. Persistence failures abort the Phase 3 node because partial writes would corrupt run audit.

## Testing Strategy

Use TDD in the implementation plan.

- Migration and ORM tests verify the three reference tables, nullable `object_entry_id`, uniqueness, and indexes.
- Import parser tests use tiny fixture files for HGNC, OMIM, HPO, ClinGen, and ClinVar.
- Matcher tests cover unique exact matches, alias matches, OMIM disease priority, MONDO fallback, ClinVar 0-star exclusion, ambiguous aliases, and unmapped candidates.
- Adapter tests cover EvidenceChain-first candidate extraction and phenotype extraction from evidence items.
- Service tests use a fake repository to verify persistence decisions and canonical update priority.
- Integration tests run a small DualEvidenceExtractionResult through the Phase 3 facade.

## Risks

- ClinVar `variant_summary.txt` is large. Import must stream rows and batch writes.
- OMIM disease parsing is heterogeneous. MVP should preserve raw payload and only create relationships when both sides resolve deterministically.
- MONDO entries from ClinGen are partial. They must be marked source-limited in `raw_payload`.
- Variant HGVS strings in ClinVar `Name` are not guaranteed to be clean. MVP only accepts exact aliases generated during import.
- Existing dirty worktree changes must not be included in the Phase 3 implementation commits unless they are explicitly part of that task.
