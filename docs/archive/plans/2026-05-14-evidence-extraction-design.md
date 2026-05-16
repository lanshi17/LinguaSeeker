# Evidence Extraction Design

**Status:** completed
**Created:** 2026-05-14
**Completed:** 2026-05-15
**PR:** merged

## Goal

Build a reusable evidence extraction block that reads one already-formatted document track and extracts GDV/ACMG guideline evidence items and evidence chains with source grounding.

## Approved Scope

In scope:

- Implement only the `extract_evidence` block under `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/`.
- Accept one prepared track document at a time.
- Support `track="original"` and `track="translated"` through the same track-agnostic extractor.
- Extract the complete 10-category GDV/ACMG evidence catalog.
- Return structured evidence items, evidence chains, specialized evidence records, and a quality report.
- Use LangGraph typed state and LangChain structured output.
- Add an evidence-extraction config domain.
- Validate and repair source spans against upstream-provided document spans.

Out of scope:

- Formatting.
- Translation.
- Database writes.
- FastAPI routes.
- Offline public database correction.
- Original-vs-translated comparison.
- ACMG/GDV scoring or classification.
- Module README during implementation. Use `skill:module-guide` after implementation and tests pass.

## Architecture

Use a layered facade design.

```text
api.py        EvidenceExtractionService facade
workflow.py   LangGraph wiring only
contracts.py  Pydantic state, request/result, source, item, chain contracts
catalog.py    Static 10-category EvidenceFieldSpec registry
providers.py  LangChain ChatOpenAI structured-output provider
prompts.py    Prompt builders
core.py       Source grounding, quality validation, intra-track conflict checks
stages/       One small component per runtime stage
```

The orchestrator only controls graph topology and state transitions. Stage modules own extraction behavior. Pure deterministic rules live in `core.py`. The catalog is the single source of truth for evidence fields.

## Runtime Pipeline

The first runtime version uses 5 stages, not 10 hard nodes. The original 10-stage outline remains domain guidance, but the implementation topology stays smaller and easier to test.

1. `DocumentEvidenceMap`
   - Structured LLM output.
   - Combines relevance scan, terminology discovery, structure map, and location hints for cases, experiments, authority sources, and contradictions.
   - `relevant=false` returns `status="not_relevant"` normally.

2. `CatalogExtraction`
   - Structured LLM output.
   - Uses the static 10-category GDV/ACMG catalog.
   - Extracts evidence items and evidence chains for the current track.
   - Missing fields are retained as `status="not_found"`.
   - Does not score or classify evidence.

3. `SpecialEvidencePass`
   - Structured LLM output.
   - Focuses on functional experiments, case-control evidence, authority/reference assertions, and contradiction/exclusion evidence.
   - Can add or strengthen evidence chains, but cannot overwrite traceable extraction facts without recording the source.

4. `SourceGrounding`
   - Rule-based source validation and repair.
   - Validates source spans against `TrackDocument.formatted_text` and `TrackDocument.page_spans`.
   - If snippet and offset mismatch, searches the document and updates `span_id`, `page`, `start_offset`, and `end_offset`.
   - If the same snippet appears multiple times, asks the LLM to select the best source. If still uncertain, marks the source as ambiguous.
   - Saves `raw_source` only when a source was corrected, reviewed, or marked ambiguous.

5. `QualityValidation`
   - Rule-based validation.
   - Every `found` item must have a valid source.
   - Required missing evidence marks `scorable=false`.
   - Summarizes low-confidence items, invalid or ambiguous sources, contradictions, and expert-review needs.

## Input Contract

`extract_evidence` consumes upstream-formatted text. It does not format, translate, or build page spans.

```python
class Track(str, Enum):
    ORIGINAL = "original"
    TRANSLATED = "translated"


class ExternalIds(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    pmcid: str | None = None


class PageSpan(BaseModel):
    span_id: str
    page: int
    start_offset: int
    end_offset: int


class TrackDocument(BaseModel):
    document_id: str
    track: Track
    formatted_text: str
    page_spans: list[PageSpan]
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    metadata: dict[str, str] = Field(default_factory=dict)
```

`PageSpan` coordinate semantics are owned by the upstream formatter. Extraction consumes and validates them.

## Evidence Contract

```python
class SourcePrecision(str, Enum):
    EXACT = "exact"
    CORRECTED = "corrected"
    AMBIGUOUS = "ambiguous"


class SourceLocation(BaseModel):
    span_id: str
    page: int
    start_offset: int
    end_offset: int
    context_type: Literal["text", "table", "figure", "supplementary", "caption"]
    context_ref: str
    text_snippet: str
    source_precision: SourcePrecision


class EvidenceStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    SOURCE_INVALID = "source_invalid"


class EvidenceItem(BaseModel):
    field_id: str
    category: str
    field_name: str
    status: EvidenceStatus
    value: str | int | float | bool | list[str] | None
    acmg_codes: list[str]
    clingen_modules: list[str]
    source: SourceLocation | None = None
    raw_source: SourceLocation | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""
```

## Evidence Chains

An `EvidenceChain` groups related `EvidenceItem` records for a gene-disease-variant/case relationship. It records what the literature supports, which source spans support it, and which guideline concepts it feeds downstream. It does not score or classify.

The chain should be able to reference:

- Gene text or internal gene ID if available.
- Disease text or internal disease ID if available.
- Variant text or internal variant ID if available.
- Case/proband ID if available.
- Evidence item field IDs.
- Contradictions and quality warnings.

## LLM And Configuration

Add a new config domain:

```python
class EvidenceExtractionConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    fast_model: str = ""
    standard_model: str = ""
    strong_model: str = ""
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3
```

Environment variables:

- `EVIDENCE_EXTRACTION_API_KEY`
- `EVIDENCE_EXTRACTION_BASE_URL`
- `EVIDENCE_EXTRACTION_FAST_MODEL`
- `EVIDENCE_EXTRACTION_STANDARD_MODEL`
- `EVIDENCE_EXTRACTION_STRONG_MODEL`
- `EVIDENCE_EXTRACTION_TEMPERATURE`
- `EVIDENCE_EXTRACTION_TIMEOUT`
- `EVIDENCE_EXTRACTION_MAX_RETRIES`

Provider behavior:

- Follow the existing `MultiStageTranslator` style.
- Use `ChatOpenAI`.
- Use `.with_structured_output(PydanticModel, method="json_schema")` where supported.
- Support a provider-level fallback to JSON mode for OpenAI-compatible backends that do not support native JSON schema.
- Retry structured parse/schema failures once.
- Retry transient network/rate-limit failures twice.
- Fail fast after retries.

Model selection:

- Evidence map: fast model.
- Catalog extraction: strong model.
- Special evidence pass: strong model.
- Source ambiguity review: standard model.
- Quality validation: no LLM.

## Testing

Use `uv run pytest`.

Test with fake LLM provider by default. Add one real LLM integration test marked `@pytest.mark.integration`, skipped unless evidence extraction env vars are present.

Core test coverage:

- Contracts and validation.
- Full catalog registry validity.
- Facade initialization.
- LangGraph state transitions.
- `not_relevant` early exit.
- Catalog extraction normalization.
- Source grounding exact match.
- Source grounding corrected match.
- Duplicate snippet ambiguity review.
- Quality failure for `found` item without source.
- `scorable=false` for missing required items.

## Documentation

This design document and the implementation plan are planning artifacts. Do not write the module README during implementation planning. After implementation and tests pass, use `skill:module-guide` to generate the developer guide for the implemented module.

