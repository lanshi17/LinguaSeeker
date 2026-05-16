# Cross-Lingual Document Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist original/translated markdown documents and associated images from the cross-lingual module to local storage, and expose a typed output schema for downstream consumers.

**Architecture:** Add a persistence layer to the cross-lingual module. A `DocumentPersistenceService` handles file I/O (markdown + images) to a local output directory. The `PipelineState` is extended with `image_paths` so images flow through the LangGraph. A `CrossLingualOutput` Pydantic model serves as the typed contract passed to downstream modules (Phase 3: standardize entities).

**Tech Stack:** Python, Pydantic, pathlib, loguru, pytest

---
**Status:** completed
**Created:** 2026-05-14
**Completed:** 2026-05-14
**PR:** merged

## Context

### Current State

- `TranslationService.run(pages)` returns `TranslationResult` with `formatted_original` (str) and `translated_english` (str) as in-memory strings.
- `PipelineState` carries `pages`, `formatted`, `translation_result` — but no image paths.
- Upstream `ParseResult.pages` contains `FigurePosition` (page, index, caption) and MinerU output zip contains actual image files referenced via `img_path` in markdown.
- No persistence exists in the cross-lingual module. The old version (`PipelineFiles` in `.old_version/src/domain/models.py`) used MinIO — we need local storage first.

### Key Files

| File | Role |
|---|---|
| `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py` | Data contracts (PipelineState, TranslationResult, etc.) |
| `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py` | LangGraph orchestrator + TranslationService |
| `backend/src/core/cross_lingual_process_and_extract_evidence/config_context.py` | LLM config injection |
| `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py` | MarkdownFormatter |
| `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py` | MultiStageTranslator |
| `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py` | ParseResult, PageContent, FigurePosition |
| `backend/src/core/config.py` | Settings singleton |

### Data Flow (After)

```
ParseResult.pages ──┐
                    ▼
              TranslationService.run()
                    │
                    ▼
            TranslationResult
                    │
                    ▼
        DocumentPersistenceService.save()
                    │
                    ├── output_dir/
                    │   ├── original.md
                    │   ├── translated.md
                    │   ├── metadata.json
                    │   └── images/
                    │       ├── page1_fig1.png
                    │       └── ...
                    ▼
            CrossLingualOutput ──→ downstream (Phase 3)
```

---

## Task 1: Extend contracts with persistence and output types

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py`

**Step 1: Write the failing tests**

```python
# Add to existing test_contracts.py

def test_saved_documents_fields():
    """SavedDocuments tracks output file paths."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import SavedDocuments
    from pathlib import Path
    from datetime import datetime, timezone

    saved = SavedDocuments(
        original_md_path=Path("/tmp/out/original.md"),
        translated_md_path=Path("/tmp/out/translated.md"),
        metadata_path=Path("/tmp/out/metadata.json"),
        image_dir=Path("/tmp/out/images"),
        image_paths=[Path("/tmp/out/images/fig1.png")],
        output_dir=Path("/tmp/out"),
        created_at=datetime.now(timezone.utc),
    )
    assert saved.original_md_path.name == "original.md"
    assert len(saved.image_paths) == 1


def test_cross_lingual_output_fields():
    """CrossLingualOutput is the downstream contract."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import CrossLingualOutput

    out = CrossLingualOutput(
        formatted_original="原始文本",
        translated_english="Original text",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        saved_dir="/tmp/out",
        original_md_path="/tmp/out/original.md",
        translated_md_path="/tmp/out/translated.md",
        image_paths=["/tmp/out/images/fig1.png"],
    )
    assert out.source_language == "zh"
    assert out.terminology_map["基因"] == "gene"
    assert len(out.image_paths) == 1


def test_pipeline_state_image_paths():
    """PipelineState carries image_paths from upstream."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import PipelineState

    state = PipelineState(pages=[], image_paths=["/data/img1.png", "/data/img2.png"])
    assert len(state.image_paths) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v -k "saved_documents or cross_lingual_output or pipeline_state_image" 2>&1 | tail -20`
Expected: FAIL — `SavedDocuments`, `CrossLingualOutput` not defined, `image_paths` field missing from `PipelineState`

**Step 3: Implement the contracts**

Add to `contracts.py`:

```python
from datetime import datetime
from pathlib import Path


@dataclass
class SavedDocuments:
    """Result of persisting cross-lingual documents to storage."""

    original_md_path: Path
    translated_md_path: Path
    metadata_path: Path
    image_dir: Path
    image_paths: List[Path]
    output_dir: Path
    created_at: datetime


class CrossLingualOutput(BaseModel):
    """Typed output contract passed to downstream modules.

    This is the authoritative schema that Phase 3 (standardize entities)
    receives from Phase 2 (cross-lingual processing).
    """

    formatted_original: str
    translated_english: str
    source_language: str
    terminology_map: Dict[str, str]
    translation_warnings: List[str]
    saved_dir: str
    original_md_path: str
    translated_md_path: str
    image_paths: List[str]
```

Add `image_paths` field to `PipelineState`:

```python
class PipelineState(BaseModel):
    # ... existing fields ...
    image_paths: List[str] = Field(default_factory=list)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py -v -k "saved_documents or cross_lingual_output or pipeline_state_image" 2>&1 | tail -20`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py backend/tests/core/cross_lingual_process_and_extract_evidence/test_contracts.py
git commit -m "feat: add SavedDocuments, CrossLingualOutput contracts and image_paths to PipelineState"
```

---

## Task 2: Implement DocumentPersistenceService

**Files:**
- Create: `backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py`

**Step 1: Write the failing tests**

```python
# tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py
"""Tests for document persistence service."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationResult,
    SentenceRegion,
    SavedDocuments,
)
from src.core.cross_lingual_process_and_extract_evidence.persistence import (
    DocumentPersistenceService,
)


def _make_result(
    original: str = "原始文本内容",
    translated: str = "Original text content",
    lang: str = "zh",
) -> TranslationResult:
    return TranslationResult(
        formatted_original=original,
        translated_english=translated,
        source_language=lang,
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )


class TestDocumentPersistenceService:
    def test_save_creates_markdown_files(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.original_md_path.exists()
        assert saved.translated_md_path.exists()
        assert saved.original_md_path.read_text(encoding="utf-8") == "原始文本内容"
        assert saved.translated_md_path.read_text(encoding="utf-8") == "Original text content"

    def test_save_creates_metadata_json(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.metadata_path.exists()
        meta = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        assert meta["doc_id"] == "doc001"
        assert meta["source_language"] == "zh"
        assert meta["terminology_map"] == {"基因": "gene"}

    def test_save_copies_images(self, tmp_path: Path):
        # Create fake source images
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        img1 = src_dir / "fig1.png"
        img1.write_bytes(b"fake_png_1")
        img2 = src_dir / "fig2.png"
        img2.write_bytes(b"fake_png_2")

        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(
            result,
            output_dir=str(tmp_path / "out"),
            doc_id="doc001",
            image_paths=[str(img1), str(img2)],
        )

        assert len(saved.image_paths) == 2
        for p in saved.image_paths:
            assert p.exists()
            assert p.read_bytes() in (b"fake_png_1", b"fake_png_2")
        assert saved.image_dir.exists()

    def test_save_no_images(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.image_paths == []
        assert saved.image_dir.exists()  # dir still created

    def test_save_output_dir_structure(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path / "out"), doc_id="doc001")

        assert saved.output_dir == tmp_path / "out" / "doc001"
        assert saved.output_dir.exists()

    def test_to_output(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")
        output = service.to_output(result, saved)

        assert output.formatted_original == "原始文本内容"
        assert output.translated_english == "Original text content"
        assert output.saved_dir == str(saved.output_dir)
        assert output.original_md_path == str(saved.original_md_path)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py -v 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.cross_lingual_process_and_extract_evidence.persistence'`

**Step 3: Implement DocumentPersistenceService**

Create `backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py`:

```python
"""Local file persistence for cross-lingual documents and images."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from loguru import logger

from .contracts import (
    CrossLingualOutput,
    SavedDocuments,
    TranslationResult,
)


class DocumentPersistenceService:
    """Persists TranslationResult to local filesystem.

    Output structure::

        <output_dir>/<doc_id>/
            original.md
            translated.md
            metadata.json
            images/
                page1_fig1.png
                ...
    """

    def save(
        self,
        result: TranslationResult,
        output_dir: str,
        doc_id: str,
        image_paths: List[str] | None = None,
    ) -> SavedDocuments:
        """Save translation result and images to local directory.

        Args:
            result: The TranslationResult from the pipeline.
            output_dir: Root output directory.
            doc_id: Unique document identifier (used as subdirectory name).
            image_paths: Optional list of source image file paths to copy.

        Returns:
            SavedDocuments with paths to all saved files.
        """
        base = Path(output_dir) / doc_id
        base.mkdir(parents=True, exist_ok=True)

        # Write markdown files
        original_path = base / "original.md"
        original_path.write_text(result.formatted_original, encoding="utf-8")
        logger.info("Saved original markdown: {}", original_path)

        translated_path = base / "translated.md"
        translated_path.write_text(result.translated_english, encoding="utf-8")
        logger.info("Saved translated markdown: {}", translated_path)

        # Write metadata
        metadata = {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "terminology_map": result.terminology_map,
            "translation_warnings": result.translation_warnings,
            "sentence_count": len(result.sentences),
            "segment_count": len(result.segments),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = base / "metadata.json"
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved metadata: {}", meta_path)

        # Copy images
        image_dir = base / "images"
        image_dir.mkdir(exist_ok=True)
        saved_image_paths: List[Path] = []
        for src in image_paths or []:
            src_path = Path(src)
            if not src_path.exists():
                logger.warning("Image not found, skipping: {}", src)
                continue
            dst = image_dir / src_path.name
            shutil.copy2(src_path, dst)
            saved_image_paths.append(dst)
            logger.debug("Copied image: {} -> {}", src_path, dst)

        if saved_image_paths:
            logger.info("Copied {} images to {}", len(saved_image_paths), image_dir)

        return SavedDocuments(
            original_md_path=original_path,
            translated_md_path=translated_path,
            metadata_path=meta_path,
            image_dir=image_dir,
            image_paths=saved_image_paths,
            output_dir=base,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def to_output(
        result: TranslationResult,
        saved: SavedDocuments,
    ) -> CrossLingualOutput:
        """Convert to downstream output contract."""
        return CrossLingualOutput(
            formatted_original=result.formatted_original,
            translated_english=result.translated_english,
            source_language=result.source_language,
            terminology_map=result.terminology_map,
            translation_warnings=result.translation_warnings,
            saved_dir=str(saved.output_dir),
            original_md_path=str(saved.original_md_path),
            translated_md_path=str(saved.translated_md_path),
            image_paths=[str(p) for p in saved.image_paths],
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py -v 2>&1 | tail -30`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py backend/tests/core/cross_lingual_process_and_extract_evidence/test_persistence.py
git commit -m "feat: add DocumentPersistenceService for local file persistence"
```

---

## Task 3: Wire persistence into TranslationService

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py`
- Test: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py`

**Step 1: Write the failing tests**

```python
# Add to existing test_workflow.py

@pytest.mark.asyncio
async def test_translation_service_save(tmp_path):
    """TranslationService.save() persists result and returns output."""
    from unittest.mock import MagicMock, patch

    cfg = MagicMock()
    cfg.translation.model = "test-model"
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001"

    service = TranslationService(cfg=cfg)

    # Mock the pipeline to avoid LLM calls
    mock_result = TranslationResult(
        formatted_original="原始文本",
        translated_english="Original text",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )

    with patch.object(service, "run", return_value=mock_result):
        result = await service.run([{"page_number": 1, "markdown": "原始文本"}])
        output = service.save(
            result,
            output_dir=str(tmp_path),
            doc_id="test_doc",
        )

        assert output.formatted_original == "原始文本"
        assert output.translated_english == "Original text"
        assert output.saved_dir.startswith(str(tmp_path))
        assert output.original_md_path.endswith("original.md")
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v -k "translation_service_save" 2>&1 | tail -20`
Expected: FAIL — `AttributeError: 'TranslationService' object has no attribute 'save'`

**Step 3: Add save method to TranslationService**

Add to `workflow.py`:

```python
from .persistence import DocumentPersistenceService
from .contracts import CrossLingualOutput
```

Add to `TranslationService.__init__`:

```python
self._persistence = DocumentPersistenceService()
```

Add method to `TranslationService`:

```python
def save(
    self,
    result: TranslationResult,
    output_dir: str,
    doc_id: str,
    image_paths: list[str] | None = None,
) -> CrossLingualOutput:
    """Persist result to local storage and return downstream output contract.

    Args:
        result: TranslationResult from run().
        output_dir: Root output directory.
        doc_id: Unique document identifier.
        image_paths: Optional source image paths to copy.

    Returns:
        CrossLingualOutput for downstream consumers.
    """
    saved = self._persistence.save(result, output_dir, doc_id, image_paths)
    return self._persistence.to_output(result, saved)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py -v -k "translation_service_save" 2>&1 | tail -20`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py backend/tests/core/cross_lingual_process_and_extract_evidence/test_workflow.py
git commit -m "feat: wire DocumentPersistenceService into TranslationService"
```

---

## Task 4: Add output_dir config and integrate with existing tests

**Files:**
- Modify: `backend/src/core/config.py` (add `cross_lingual_output_dir` field)
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py` (if exists, add persistence integration)

**Step 1: Add config field**

Add to `Settings` in `config.py`:

```python
# ── Cross-lingual output ─────────────────────────────────────────────
cross_lingual_output_dir: str = "data/cross_lingual_output"
```

**Step 2: Run existing tests to verify no regression**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v 2>&1 | tail -30`
Expected: All existing tests PASS

**Step 3: Commit**

```bash
git add backend/src/core/config.py
git commit -m "feat: add cross_lingual_output_dir config field"
```

---

## Task 5: Run full test suite and verify

**Files:**
- No new files

**Step 1: Run all cross_lingual tests**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v 2>&1 | tail -40`
Expected: All tests PASS

**Step 2: Run ruff lint check**

Run: `cd backend && uv run ruff check src/core/cross_lingual_process_and_extract_evidence/ 2>&1`
Expected: No errors

**Step 3: Final commit (if any lint fixes needed)**

```bash
git add -u
git commit -m "fix: lint fixes for cross_lingual persistence module"
```

---

## Summary of Changes

| File | Action | Description |
|---|---|---|
| `contracts.py` | Modify | Add `SavedDocuments`, `CrossLingualOutput`, `image_paths` to `PipelineState` |
| `persistence.py` | Create | `DocumentPersistenceService` — local file I/O for markdown + images |
| `workflow.py` | Modify | Add `save()` method to `TranslationService`, inject `DocumentPersistenceService` |
| `config.py` | Modify | Add `cross_lingual_output_dir` setting |
| `test_contracts.py` | Modify | Tests for new contract types |
| `test_persistence.py` | Create | Tests for `DocumentPersistenceService` |
| `test_workflow.py` | Modify | Tests for `TranslationService.save()` |
