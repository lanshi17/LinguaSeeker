# Evidence Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable track-agnostic evidence extraction module that extracts GDV/ACMG evidence items and evidence chains from one upstream-formatted document track.

**Architecture:** Use a layered facade design. `EvidenceExtractionService` is the public entry point, `workflow.py` owns LangGraph wiring only, stage modules own LLM extraction, `catalog.py` is the evidence field source of truth, and `core.py` owns deterministic source grounding and quality validation.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, LangChain `ChatOpenAI.with_structured_output`, loguru, pytest, pytest-asyncio, uv.

---

**Status:** completed
**Created:** 2026-05-14
**Completed:** 2026-05-15
**PR:** merged

## Scope

In scope:

- New package: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/`.
- One-track extraction for `track="original"` or `track="translated"`.
- Full 10-category GDV/ACMG evidence catalog.
- Five runtime stages: evidence map, catalog extraction, special evidence pass, source grounding, quality validation.
- LangGraph typed state.
- LangChain structured output.
- Source span validation and repair.
- Mocked unit tests plus one real LLM integration test.

Out of scope:

- Formatting.
- Translation.
- Original-vs-translated comparison.
- Database writes.
- Offline public database correction.
- FastAPI routes.
- ACMG/GDV scoring.
- Module README before implementation completion.

## Implementation Tasks

### Task 1: Evidence Extraction Config

**Files:**

- Modify: `backend/src/core/config.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/config_context.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_config_context.py`

**Step 1: Write the failing config tests**

```python
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)


def test_evidence_extraction_config_context_from_config():
    cfg = MagicMock()
    cfg.evidence_extraction.api_key = "key"
    cfg.evidence_extraction.base_url = "http://localhost:8001/v1"
    cfg.evidence_extraction.fast_model = "qwen-flash"
    cfg.evidence_extraction.standard_model = "qwen-plus"
    cfg.evidence_extraction.strong_model = "qwen-max"
    cfg.evidence_extraction.temperature = 0.0
    cfg.evidence_extraction.timeout = 60
    cfg.evidence_extraction.max_retries = 3

    ctx = EvidenceExtractionConfigContext.from_config(cfg)

    assert ctx.fast_model == "qwen-flash"
    assert ctx.standard_model == "qwen-plus"
    assert ctx.strong_model == "qwen-max"
    assert ctx.timeout == 60
    assert ctx.max_retries == 3
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_config_context.py -q
```

Expected: FAIL because `extract_evidence.config_context` does not exist.

**Step 3: Add config model and context**

In `backend/src/core/config.py`, add:

```python
class EvidenceExtractionConfig(BaseModel):
    """Evidence extraction LLM settings."""

    api_key: str = ""
    base_url: str = ""
    fast_model: str = ""
    standard_model: str = ""
    strong_model: str = ""
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3
```

Add flat fields to `Settings`:

```python
evidence_extraction_api_key: str = ""
evidence_extraction_base_url: str = ""
evidence_extraction_fast_model: str = ""
evidence_extraction_standard_model: str = ""
evidence_extraction_strong_model: str = ""
evidence_extraction_temperature: float = 0.0
evidence_extraction_timeout: int = 60
evidence_extraction_max_retries: int = 3
```

Add the nested model field:

```python
evidence_extraction: EvidenceExtractionConfig = Field(
    default_factory=EvidenceExtractionConfig,
    exclude=True,
)
```

Build it in `_build_nested()`:

```python
self.evidence_extraction = EvidenceExtractionConfig(
    api_key=self.evidence_extraction_api_key,
    base_url=self.evidence_extraction_base_url,
    fast_model=self.evidence_extraction_fast_model,
    standard_model=self.evidence_extraction_standard_model,
    strong_model=self.evidence_extraction_strong_model,
    temperature=self.evidence_extraction_temperature,
    timeout=self.evidence_extraction_timeout,
    max_retries=self.evidence_extraction_max_retries,
)
```

Create `config_context.py`:

```python
"""Typed config context for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceExtractionConfigContext:
    """Subset of app config needed by the evidence extraction module."""

    api_key: str
    base_url: str
    fast_model: str
    standard_model: str
    strong_model: str
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_config(cls, cfg: Any) -> EvidenceExtractionConfigContext:
        evidence_cfg = cfg.evidence_extraction
        return cls(
            api_key=evidence_cfg.api_key,
            base_url=evidence_cfg.base_url,
            fast_model=evidence_cfg.fast_model,
            standard_model=evidence_cfg.standard_model,
            strong_model=evidence_cfg.strong_model,
            temperature=evidence_cfg.temperature,
            timeout=evidence_cfg.timeout,
            max_retries=evidence_cfg.max_retries,
        )
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_config_context.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/config.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/config_context.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_config_context.py
git commit -m "feat: add evidence extraction config"
```

### Task 2: Core Contracts

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py`

**Step 1: Write failing contract tests**

```python
import pytest
from pydantic import ValidationError

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    ExternalIds,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)


def test_track_document_accepts_upstream_spans():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 has BRCA1 c.68_69delAG.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=36)],
        external_ids=ExternalIds(pmid="123"),
    )

    assert doc.track == Track.ORIGINAL
    assert doc.page_spans[0].span_id == "p1"


def test_evidence_item_found_requires_confidence_in_range():
    source = SourceLocation(
        span_id="p1",
        page=1,
        start_offset=14,
        end_offset=19,
        context_type="text",
        context_ref="Results paragraph 1",
        text_snippet="BRCA1",
        source_precision=SourcePrecision.EXACT,
    )

    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        acmg_codes=[],
        clingen_modules=["variant_evidence"],
        source=source,
        confidence=0.95,
    )

    assert item.source == source


def test_evidence_item_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            acmg_codes=[],
            clingen_modules=[],
            confidence=1.5,
        )
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py -q
```

Expected: FAIL because contracts do not exist.

**Step 3: Implement contracts**

Create `contracts.py` with Pydantic models for:

- `Track`
- `ExternalIds`
- `PageSpan`
- `TrackDocument`
- `SourcePrecision`
- `SourceLocation`
- `EvidenceStatus`
- `EvidenceItem`
- `EvidenceChain`
- `DocumentEvidenceMap`
- `SpecialEvidenceRecord`
- `QualityIssue`
- `QualityReport`
- `EvidenceExtractionStatus`
- `EvidenceExtractionResult`
- `EvidenceExtractionState`

Use this skeleton:

```python
"""Contracts for evidence extraction."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_offsets(self) -> PageSpan:
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")
        return self


class TrackDocument(BaseModel):
    document_id: str
    track: Track
    formatted_text: str
    page_spans: list[PageSpan]
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    metadata: dict[str, str] = Field(default_factory=dict)


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
    source_precision: SourcePrecision = SourcePrecision.EXACT


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
    acmg_codes: list[str] = Field(default_factory=list)
    clingen_modules: list[str] = Field(default_factory=list)
    source: SourceLocation | None = None
    raw_source: SourceLocation | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""
```

Add the remaining result/state models in the same file. Avoid function return annotations like `-> dict`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/__init__.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_contracts.py
git commit -m "feat: add evidence extraction contracts"
```

### Task 3: Static Evidence Catalog

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py`

**Step 1: Write failing catalog tests**

```python
from collections import Counter

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    EVIDENCE_FIELD_SPECS,
    get_field_spec,
)


def test_catalog_has_expected_category_counts():
    counts = Counter(spec.category_id for spec in EVIDENCE_FIELD_SPECS)

    assert counts == {
        "A": 18,
        "B": 22,
        "C": 18,
        "D": 9,
        "E": 8,
        "F": 17,
        "G": 12,
        "H": 10,
        "I": 18,
        "J": 6,
    }


def test_catalog_field_ids_are_unique():
    field_ids = [spec.field_id for spec in EVIDENCE_FIELD_SPECS]
    assert len(field_ids) == len(set(field_ids))


def test_catalog_lookup_returns_spec():
    spec = get_field_spec("A.variant_type")
    assert spec.field_id == "A.variant_type"
    assert "PVS1" in spec.acmg_codes
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -q
```

Expected: FAIL because `catalog.py` does not exist.

**Step 3: Implement catalog**

Use a frozen dataclass:

```python
"""Static GDV/ACMG evidence field catalog."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceFieldSpec:
    field_id: str
    category_id: str
    category_name: str
    field_name: str
    description: str
    acmg_codes: tuple[str, ...] = ()
    clingen_modules: tuple[str, ...] = ()
    required_for_scorable: bool = False
    expected_value_type: str = "text"


EVIDENCE_FIELD_SPECS: tuple[EvidenceFieldSpec, ...] = (
    # Paste the complete catalog from Appendix A exactly.
)


_FIELD_BY_ID = {spec.field_id: spec for spec in EVIDENCE_FIELD_SPECS}


def get_field_spec(field_id: str) -> EvidenceFieldSpec:
    return _FIELD_BY_ID[field_id]
```

Implement all 138 fields from Appendix A. Mark these as `required_for_scorable=True`:

- `B.disease_diagnosis`
- `B.diagnosis_sufficiency`
- `A.gene_symbol`
- `A.variant_hgvs_c`
- `A.variant_hgvs_p`
- `D.allele_frequency`

If a document reports only protein-level or genomic-level variants and no cDNA field, the extractor should still preserve the missing item as `not_found`; downstream scoring decides whether it is usable.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/catalog.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_catalog.py
git commit -m "feat: add evidence field catalog"
```

### Task 4: Prompt Builders

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py`

**Step 1: Write failing prompt tests**

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    get_catalog_extraction_prompt,
    get_evidence_map_prompt,
)


def test_evidence_map_prompt_mentions_no_scoring():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "Do not score" in prompt
    assert "doc-1" in prompt


def test_catalog_prompt_includes_catalog_field_ids():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "A.variant_type" in prompt
    assert "status" in prompt
    assert "not_found" in prompt
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q
```

Expected: FAIL because `prompts.py` does not exist.

**Step 3: Implement prompt builders**

Create functions:

- `get_evidence_map_prompt(...) -> str`
- `get_catalog_extraction_prompt(...) -> str`
- `get_special_evidence_prompt(...) -> str`
- `get_source_ambiguity_review_prompt(...) -> str`

Prompt rules:

- Say "Do not score or classify ACMG/GDV evidence."
- Require structured output matching the Pydantic schema.
- Require `status="not_found"` when absent.
- Require source spans for `found` items.
- Include the field catalog in compact text form.
- Include upstream page span summaries.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_prompts.py
git commit -m "feat: add evidence extraction prompts"
```

### Task 5: LangChain Structured Output Provider

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_providers.py`

**Step 1: Write failing provider tests**

```python
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
    LangChainEvidenceProvider,
)


class DemoSchema(BaseModel):
    answer: str


def test_provider_uses_strong_model_for_strong_tier():
    ctx = EvidenceExtractionConfigContext(
        api_key="key",
        base_url="http://localhost:8001/v1",
        fast_model="fast",
        standard_model="standard",
        strong_model="strong",
    )

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers.ChatOpenAI"
    ) as chat_cls:
        chat = MagicMock()
        structured = MagicMock()
        structured.invoke.return_value = DemoSchema(answer="ok")
        chat.with_structured_output.return_value = structured
        chat_cls.return_value = chat

        provider = LangChainEvidenceProvider(ctx)
        result = provider.invoke_structured(
            prompt="Return JSON.",
            output_schema=DemoSchema,
            tier=EvidenceModelTier.STRONG,
            stage="demo",
        )

    assert result.answer == "ok"
    chat_cls.assert_called_with(
        model="strong",
        api_key=provider._secret,
        base_url="http://localhost:8001/v1",
        temperature=0.0,
        timeout=60,
    )
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_providers.py -q
```

Expected: FAIL because provider does not exist.

**Step 3: Implement provider**

Follow the current translator style but keep it in the evidence module:

```python
"""LLM provider for structured evidence extraction."""
from __future__ import annotations

from enum import Enum
from typing import TypeVar

import httpx
import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, SecretStr

from .config_context import EvidenceExtractionConfigContext


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class EvidenceModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    STRONG = "strong"


class LangChainEvidenceProvider:
    """Structured-output LLM provider for evidence extraction stages."""

    _TRANSIENT_EXCEPTIONS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def __init__(self, ctx: EvidenceExtractionConfigContext):
        self._ctx = ctx
        self._secret = SecretStr(ctx.api_key)

    def _model_for_tier(self, tier: EvidenceModelTier) -> str:
        if tier == EvidenceModelTier.FAST:
            return self._ctx.fast_model
        if tier == EvidenceModelTier.STANDARD:
            return self._ctx.standard_model
        return self._ctx.strong_model

    def invoke_structured(
        self,
        prompt: str,
        output_schema: type[SchemaT],
        tier: EvidenceModelTier,
        stage: str,
    ) -> SchemaT:
        model_name = self._model_for_tier(tier)
        llm = ChatOpenAI(
            model=model_name,
            api_key=self._secret,
            base_url=self._ctx.base_url,
            temperature=self._ctx.temperature,
            timeout=self._ctx.timeout,
        )
        structured = llm.with_structured_output(output_schema, method="json_schema")
        last_exc: Exception | None = None
        for attempt in range(1, self._ctx.max_retries + 1):
            try:
                return structured.invoke([HumanMessage(content=prompt)])
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning("Stage {} transient failure {}/{}: {}", stage, attempt, self._ctx.max_retries, exc)
            except Exception as exc:
                last_exc = exc
                if attempt >= 2:
                    break
                logger.warning("Stage {} structured output failure {}/2: {}", stage, attempt, exc)
        raise RuntimeError(f"Stage {stage} failed structured output") from last_exc
```

If the project model backend cannot support `method="json_schema"`, add a targeted fallback inside this provider only. Do not scatter fallback logic across stages.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_providers.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_providers.py
git commit -m "feat: add evidence extraction llm provider"
```

### Task 6: Source Grounding And Quality Rules

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py`

**Step 1: Write failing source grounding tests**

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import SourceGrounder


def _doc() -> TrackDocument:
    text = "Page one BRCA1 evidence.\n\nPage two has c.68_69delAG evidence."
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[
            PageSpan(span_id="p1", page=1, start_offset=0, end_offset=24),
            PageSpan(span_id="p2", page=2, start_offset=26, end_offset=len(text)),
        ],
    )


def test_source_grounding_keeps_exact_source():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=9,
            end_offset=14,
            context_type="text",
            context_ref="Results",
            text_snippet="BRCA1",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.source_precision == SourcePrecision.EXACT
    assert grounded[0].raw_source is None


def test_source_grounding_corrects_wrong_offset():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS cDNA",
        status=EvidenceStatus.FOUND,
        value="c.68_69delAG",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=12,
            context_type="text",
            context_ref="Table 1",
            text_snippet="c.68_69delAG",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.page == 2
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
    assert grounded[0].raw_source is not None
```

**Step 2: Write failing quality validation tests**

```python
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import QualityValidator


def test_quality_validation_flags_found_item_without_source():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.9,
    )

    report = QualityValidator(required_field_ids=set()).validate([item], contradictions=[])

    assert report.passed is False
    assert report.issues[0].issue_type == "missing_source"


def test_quality_validation_marks_unscorable_when_required_item_missing():
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )

    report = QualityValidator(required_field_ids={"B.disease_diagnosis"}).validate([item], contradictions=[])

    assert report.scorable is False
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py \
  -q
```

Expected: FAIL because `core.py` does not exist.

**Step 4: Implement source grounding and quality validation**

Implement:

- `SourceGrounder.ground_items(document, items) -> list[EvidenceItem]`
- `SourceGrounder` exact source check.
- Cross-document snippet search.
- Rebuild corrected `SourceLocation`.
- Preserve `raw_source` only on corrected/ambiguous sources.
- `QualityValidator.validate(items, contradictions) -> QualityReport`
- `IntraTrackConflictChecker.check(items) -> list[QualityIssue]`

Do not use file I/O.

**Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py \
  -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_source_grounding.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_quality_validation.py
git commit -m "feat: add evidence source grounding"
```

### Task 7: Runtime Stage Components

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/__init__.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/special_evidence.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/source_grounding.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/quality_validation.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py`

**Step 1: Write failing stage tests**

Use a fake provider with `invoke_structured(...)` returning schema instances. Test that:

- Evidence map stage calls fast tier.
- Catalog extraction stage calls strong tier.
- Special evidence stage calls strong tier.
- Source grounding stage uses `SourceGrounder`.
- Quality stage returns `QualityReport`.

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -q
```

Expected: FAIL because stage modules do not exist.

**Step 3: Implement stages**

Each stage class should have one public method, for example:

```python
class EvidenceMapStage:
    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(self, document: TrackDocument) -> DocumentEvidenceMap:
        prompt = get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text=document.formatted_text,
        )
        return self._provider.invoke_structured(
            prompt=prompt,
            output_schema=DocumentEvidenceMap,
            tier=EvidenceModelTier.FAST,
            stage="evidence_map",
        )
```

Keep stage classes thin. Put deterministic logic in `core.py`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_stages.py
git commit -m "feat: add evidence extraction stages"
```

### Task 8: LangGraph Workflow And Facade

**Files:**

- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py`
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api.py`

**Step 1: Write failing workflow tests**

```python
import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    PageSpan,
    Track,
    TrackDocument,
)


@pytest.mark.asyncio
async def test_service_returns_not_relevant(fake_stage_factory, mock_config):
    fake_stage_factory.evidence_map.relevant = False
    service = EvidenceExtractionService(cfg=mock_config, stage_factory=fake_stage_factory)

    result = await service.run(
        TrackDocument(
            document_id="doc-1",
            track=Track.ORIGINAL,
            formatted_text="unrelated paper",
            page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=15)],
        )
    )

    assert result.status == "not_relevant"
    assert result.evidence_items == []
```

Add a second test for a completed path with fake stage outputs.

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api.py \
  -q
```

Expected: FAIL because workflow and facade do not exist.

**Step 3: Implement workflow**

Use `StateGraph(EvidenceExtractionState)`.

Nodes:

- `evidence_map`
- `catalog_extraction`
- `special_evidence`
- `source_grounding`
- `quality_validation`
- `not_relevant`

Conditional edge:

- If `state.evidence_map.relevant is False`, route to `not_relevant`.
- Otherwise continue to catalog extraction.

`workflow.py` must only wire nodes and call stage delegates.

**Step 4: Implement facade**

`api.py`:

```python
class EvidenceExtractionService:
    """Public facade for one-track evidence extraction."""

    def __init__(self, cfg: Any):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._workflow = EvidenceExtractionWorkflow(provider=self._provider)

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        return await self._workflow.run(document)

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(document))
        raise RuntimeError("run_sync() cannot be called from within a running event loop. Use run() instead.")
```

Use the same async wrapper pattern as `TranslationService`.

**Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api.py \
  -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py \
  backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/api.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_workflow.py \
  backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_api.py
git commit -m "feat: add evidence extraction facade"
```

### Task 9: Integration Test

**Files:**

- Create: `backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py`

**Step 1: Write integration test**

Use `pytest.mark.integration`. Skip unless these env vars exist:

- `EVIDENCE_EXTRACTION_API_KEY`
- `EVIDENCE_EXTRACTION_BASE_URL`
- `EVIDENCE_EXTRACTION_FAST_MODEL`
- `EVIDENCE_EXTRACTION_STANDARD_MODEL`
- `EVIDENCE_EXTRACTION_STRONG_MODEL`

Test input should be a tiny formatted document with one page span:

```text
Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A (p.Gly334Ser) variant.
The variant was absent from population databases. No functional assay was reported.
```

Expected assertions:

- Result status is `completed` or `not_relevant` is false.
- At least one found evidence item has a valid source.
- Quality report is present.

**Step 2: Run integration test without env**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py -m integration -q
```

Expected: SKIPPED when env vars are absent.

**Step 3: Commit**

```bash
git add backend/tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/test_integration_real_llm.py
git commit -m "test: add evidence extraction llm integration test"
```

### Task 10: Verification

**Files:**

- No new source files.

**Step 1: Run focused tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence -q
```

Expected: PASS, with integration test skipped unless env vars are configured.

**Step 2: Run existing cross-lingual tests**

Run:

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence -q
```

Expected: PASS.

**Step 3: Run lint**

Run:

```bash
cd backend
uv run ruff check
```

Expected: PASS.

**Step 4: Commit any verification-only fixes**

Only commit fixes required by failing tests or lint. Do not refactor unrelated code.

### Task 11: Module Guide After Implementation

**Files:**

- Create or update docs generated by `skill:module-guide`.
- Update: `progress.txt`

**Step 1: Generate module guide**

After implementation and tests pass, use `skill:module-guide` for:

```text
backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence
```

Expected: A developer guide documenting public API, architecture, contracts, extension points, and testing.

**Step 2: Organize docs**

Because docs changed, use `skill:doc-organize`.

**Step 3: Update progress**

Append:

```text
[2026-05-14] Evidence extraction module implemented with track-agnostic facade, catalog extraction, source grounding, and quality validation [done]
```

**Step 4: Commit**

```bash
git add docs progress.txt
git commit -m "docs: add evidence extraction module guide"
```

## Appendix A: Complete Initial Evidence Field Catalog

Each row maps to one `EvidenceFieldSpec`. The implementation must preserve the field IDs exactly unless the domain owner revises this plan before execution.

| field_id | field_name | ACMG codes | ClinGen modules |
|---|---|---|---|
| A.gene_symbol | Gene symbol | PVS1,PP2,BP1 | variant_evidence |
| A.gene_aliases | Gene aliases or old names |  | variant_evidence |
| A.gene_disease_relationship | Reported gene-disease relationship | PP4 | variant_evidence |
| A.transcript_id | Transcript ID |  | variant_evidence |
| A.reference_sequence | Reference sequence or genome build |  | variant_evidence |
| A.variant_hgvs_c | HGVS coding variant | PS1,PM5 | variant_evidence |
| A.variant_hgvs_p | HGVS protein variant | PS1,PM5 | variant_evidence |
| A.variant_hgvs_g | HGVS genomic variant |  | variant_evidence |
| A.variant_legacy_name | Legacy or traditional variant name |  | variant_evidence |
| A.variant_type | Variant type | PVS1,BP1,BP7 | variant_evidence |
| A.null_variant_detail | Null variant detail and LoF context | PVS1 | variant_evidence |
| A.protein_effect | Protein effect description | PM4,BP3,BP7 | variant_evidence |
| A.same_amino_acid_known_variant | Same amino acid as known pathogenic variant | PS1 | variant_evidence |
| A.same_residue_other_missense | Same residue different missense pathogenic reference | PM5 | variant_evidence |
| A.functional_domain_or_hotspot | Functional domain or mutational hotspot | PM1 | variant_evidence |
| A.protein_length_change | Protein length change | PM4 | variant_evidence |
| A.repeat_region_status | Repeat region status | BP3 | variant_evidence |
| A.splice_or_synonymous_effect | Synonymous or splice effect statement | BP7 | variant_evidence |
| B.case_id | Case or proband identifier |  | phenotype_consistency |
| B.proband_status | Proband status |  | phenotype_consistency |
| B.case_count | Independent case count | PS4 | case_level |
| B.disease_diagnosis | Disease diagnosis | PP4 | phenotype_consistency |
| B.diagnosis_sufficiency | Diagnosis sufficiency |  | scoreability |
| B.phenotype_specificity | Phenotype specificity | PP4 | phenotype_consistency |
| B.hpo_terms | HPO phenotype terms | PP4 | phenotype_consistency |
| B.clinical_phenotypes | Key clinical phenotypes | PP4 | phenotype_consistency |
| B.biochemical_markers | Biochemical or laboratory markers | PP4 | phenotype_consistency |
| B.age_current_or_last_followup | Current or last follow-up age | BS2 | case_level |
| B.age_of_onset | Age of onset |  | phenotype_consistency |
| B.sex | Sex |  | variant_evidence |
| B.ancestry_or_population | Ancestry or population | PM2,BA1,BS1 | population |
| B.consanguinity | Consanguinity | PM3 | segregation |
| B.mode_of_inheritance_reported | Reported mode of inheritance | PVS1,PM3,BP2 | variant_evidence |
| B.single_genetic_etiology_claim | Single genetic etiology claim | PP4 | phenotype_consistency |
| B.alternative_diagnosis_excluded | Other diagnoses excluded | BP5 | contradiction |
| B.additional_pathogenic_variant | Additional pathogenic variant | BP5 | contradiction |
| B.testing_method | Variant testing method |  | segregation |
| B.sequencing_method_quality | Sequencing method quality |  | segregation |
| B.healthy_adult_status | Healthy adult observation | BS2 | variant_evidence |
| B.case_notes | Case notes |  | phenotype_consistency |
| C.family_id | Family identifier | PP1,BS4 | segregation |
| C.pedigree_available | Pedigree availability | PP1,BS4 | segregation |
| C.inheritance_source | Inherited or de novo source | PS2,PM6 | variant_evidence |
| C.de_novo_status | De novo status | PS2,PM6 | variant_evidence |
| C.parentage_confirmed | Parentage confirmation | PS2,PM6 | variant_evidence |
| C.maternal_genotype | Maternal genotype | PS2,PM6,BS4 | segregation |
| C.maternal_phenotype | Maternal phenotype | PS2,PM6,BS4 | segregation |
| C.paternal_genotype | Paternal genotype | PS2,PM6,BS4 | segregation |
| C.paternal_phenotype | Paternal phenotype | PS2,PM6,BS4 | segregation |
| C.phase_status | Phase status | PM3,BP2 | variant_evidence |
| C.in_trans_confirmation | In trans confirmation | PM3 | variant_evidence |
| C.cis_or_trans_context | Cis or trans context | BP2 | variant_evidence |
| C.g_plus_p_plus_count | G+/P+ count | PP1 | segregation |
| C.g_plus_p_minus_count | G+/P- count | BS4 | segregation |
| C.g_minus_p_plus_count | G-/P+ count | BS4 | segregation |
| C.g_minus_p_minus_count | G-/P- count |  | segregation |
| C.obligate_carriers | Obligate carriers | PP1 | segregation |
| C.lod_score | LOD score | PP1 | segregation |
| D.population_database_name | Population database name | PM2,BA1,BS1 | variant_evidence |
| D.allele_frequency | Allele frequency | PM2,BA1,BS1 | variant_evidence |
| D.allele_count | Allele count | PM2,BA1,BS1 | variant_evidence |
| D.allele_number | Allele number | PM2,BA1,BS1 | variant_evidence |
| D.homozygote_count | Homozygote count | BS2 | variant_evidence |
| D.population_subgroup | Population subgroup | PM2,BA1,BS1 | variant_evidence |
| D.frequency_threshold_context | Disease frequency threshold context | BA1,BS1 | variant_evidence |
| D.absent_or_rare_statement | Absent or rare population statement | PM2 | variant_evidence |
| D.healthy_carrier_observation | Healthy carrier population observation | BS2 | variant_evidence |
| E.prediction_tools_list | Prediction tools list | PP3,BP4 | computational |
| E.deleterious_prediction_summary | Deleterious prediction summary | PP3 | computational |
| E.benign_prediction_summary | Benign prediction summary | BP4 | computational |
| E.splice_prediction | Splice prediction | PP3,BP4 | computational |
| E.conservation_score | Conservation score | PP3,BP4 | computational |
| E.in_silico_consensus | In silico consensus | PP3,BP4 | computational |
| E.prediction_conflict | Computational prediction conflict | PP3,BP4 | computational |
| E.computational_evidence_notes | Computational evidence notes | PP3,BP4 | computational |
| F.assay_id | Functional assay identifier | PS3,BS3 | functional_alteration |
| F.assay_type | Functional assay type | PS3,BS3 | functional_alteration |
| F.assay_system | Functional assay system | PS3,BS3 | functional_alteration |
| F.tested_variant | Tested variant | PS3,BS3 | functional_alteration |
| F.case_level_or_gene_level | Case-level or gene-level assignment | PS3,BS3 | function |
| F.functional_result | Functional result | PS3,BS3 | functional_alteration |
| F.quantitative_result | Quantitative functional result | PS3,BS3 | functional_alteration |
| F.positive_controls | Positive controls | PS3,BS3 | functional_alteration |
| F.negative_controls | Negative controls | PS3,BS3 | functional_alteration |
| F.total_controls | Total positive plus benign controls | PS3,BS3 | functional_alteration |
| F.control_quality | Control quality | PS3,BS3 | functional_alteration |
| F.replicates_or_statistics | Replicates or functional statistics | PS3,BS3 | functional_alteration |
| F.mechanism_consistency | Mechanism consistency | PS3,BS3 | functional_alteration |
| F.patient_cell_evidence | Patient-cell functional evidence | PS3,BS3 | functional_alteration |
| F.non_patient_cell_evidence | Non-patient-cell functional evidence | PS3,BS3 | functional_alteration |
| F.functional_normal_result | Functional normal result | BS3 | functional_alteration |
| F.functional_inconclusive_result | Functional inconclusive result |  | functional_alteration |
| G.study_design | Case-control study design | PS4 | case_control |
| G.case_count | Case-control case count | PS4 | case_control |
| G.control_count | Case-control control count | PS4 | case_control |
| G.case_definition | Case definition | PS4 | case_control |
| G.control_matching | Control matching quality | PS4 | case_control |
| G.variant_count_cases | Variant count in cases | PS4 | case_control |
| G.variant_count_controls | Variant count in controls | PS4 | case_control |
| G.odds_ratio | Odds ratio | PS4 | case_control |
| G.confidence_interval | Confidence interval | PS4 | case_control |
| G.p_value | P-value | PS4 | case_control |
| G.statistical_method | Statistical method | PS4 | case_control |
| G.case_control_negative_result | Negative case-control result |  | contradiction |
| H.misdiagnosis_or_reclassification | Misdiagnosis or reclassification | BP5 | contradiction |
| H.alternative_causative_gene | Alternative causative gene | BP5 | contradiction |
| H.other_pathogenic_variant | Other pathogenic variant | BP5 | contradiction |
| H.non_segregation | Non-segregation | BS4 | contradiction |
| H.healthy_carrier_contradiction | Healthy carrier contradiction | BS2 | contradiction |
| H.population_frequency_contradiction | Population frequency contradiction | BS1 | contradiction |
| H.negative_functional_result | Negative functional result | BS3 | contradiction |
| H.negative_case_control_result | Negative case-control result |  | contradiction |
| H.animal_model_no_phenotype | Animal model no phenotype |  | contradiction |
| H.contradiction_notes | Other contradiction notes | BP5,BS4 | contradiction |
| I.gene_function_biochemical | Biochemical gene function evidence |  | function |
| I.gene_function_protein_interaction | Protein interaction evidence |  | function |
| I.gene_expression_pattern | Gene expression pattern |  | function |
| I.disease_relevant_expression | Disease-relevant expression |  | function |
| I.functional_alteration_patient_cells | Patient-cell functional alteration |  | functional_alteration |
| I.functional_alteration_non_patient_cells | Non-patient-cell functional alteration |  | functional_alteration |
| I.animal_model_type | Animal model type |  | models |
| I.animal_model_phenotype | Animal model phenotype |  | models |
| I.animal_model_genotype | Animal model genotype |  | models |
| I.cell_model_type | Cell model type |  | models |
| I.cell_model_phenotype | Cell model phenotype |  | models |
| I.model_mechanism_match | Model mechanism match |  | models |
| I.human_rescue_experiment | Human rescue experiment |  | rescue |
| I.animal_rescue_experiment | Animal rescue experiment |  | rescue |
| I.cell_rescue_experiment | Cell rescue experiment |  | rescue |
| I.rescue_result | Rescue result |  | rescue |
| I.experimental_replication | Experimental replication |  | function |
| I.gene_level_experimental_notes | Gene-level experimental notes |  | function |
| J.clinvar_assertion | ClinVar assertion | PP5,BP6 | time_validity |
| J.expert_panel_assertion | Expert panel assertion | PP5,BP6 | time_validity |
| J.authority_classification | Authority classification | PP5,BP6 | time_validity |
| J.known_pathogenic_variant_reference | Known pathogenic variant reference | PS1,PM5 | time_validity |
| J.ps1_pm5_relationship | PS1 or PM5 relationship to current variant | PS1,PM5 | time_validity |
| J.independent_publications_time_span | Independent publications and time span |  | time_validity |

## Execution Handoff

After saving this plan, choose one:

1. **Subagent-Driven (this session)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - open a new session with `executing-plans`, batch execution with checkpoints.

