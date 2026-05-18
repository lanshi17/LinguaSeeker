# Persistence JSON Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace flat `.md` persistence files with structured JSON files that preserve block-level document structure (titles, paragraphs, images, tables, equations) with bbox coordinates, referencing MinerU's `content_list.json` format.

**Architecture:** Preserve MinerU's raw content_list blocks through the pipeline (ParseResult → FormattedDocument → TranslationResult → Persistence). The existing markdown-based translation pipeline remains unchanged for LLM quality; structured blocks are maintained in parallel for JSON output. The translated JSON maps translation segments back to original block structure.

**Tech Stack:** Python, Pydantic, dataclasses, MinerU content_list.json format

---

## Context

### Current Output
```
<output_dir>/<doc_id>/
    original.md          # flat markdown
    translated.md        # flat markdown
    metadata.json        # document metadata
    original_layout.json # sentence-level drift
    translated_layout.json # segment-level drift
    images/
```

### Target Output
```
<output_dir>/<doc_id>/
    original.json        # structured blocks (replaces original.md)
    translated.json      # structured blocks with translations (replaces translated.md)
    metadata.json        # document metadata (enhanced)
    images/
```

`original_layout.json` and `translated_layout.json` are removed — their drift information is folded into `metadata.json`.

### MinerU content_list.json Format (Reference)
```json
[
  {
    "type": "text",
    "text": "The response of flow duration curves...",
    "text_level": 1,
    "bbox": [62, 480, 946, 904],
    "page_idx": 0
  },
  {
    "type": "image",
    "img_path": "images/a8ecda1c69b27e4f.jpg",
    "content": "Flow duration curves showing seasonal variations",
    "image_caption": ["Fig. 1. Annual flow duration curves."],
    "image_footnote": [],
    "bbox": [62, 480, 946, 904],
    "page_idx": 1
  },
  {
    "type": "table",
    "img_path": "images/e3cb413394a475e5.jpg",
    "table_body": "<html>...</html>",
    "table_caption": ["Table 2 Significance..."],
    "table_footnote": ["* indicates significance..."],
    "bbox": [62, 480, 946, 904],
    "page_idx": 5
  }
]
```

---

### Task 1: Add ContentBlock Contract

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`

**Step 1: Add ContentBlock dataclass**

Add after the existing `SentenceRegion` class:

```python
@dataclass
class ContentBlock:
    """A single content block following MinerU content_list.json format.

    Preserves block-level document structure (titles, paragraphs, images,
    tables, equations, etc.) with bbox coordinates for structured JSON output.
    """
    type: str  # text, title, image, table, equation, code, list, header, footer, etc.
    page_idx: int = 0
    bbox: list[int] = field(default_factory=list)  # [x0, y0, x1, y1] normalized 0-1000

    # text / title fields
    text: str = ""
    text_level: int | None = None  # heading level for title type

    # image fields
    img_path: str = ""
    content: str = ""  # image description content
    image_caption: list[str] = field(default_factory=list)
    image_footnote: list[str] = field(default_factory=list)
    sub_type: str = ""  # visual sub-type for image/chart

    # table fields
    table_body: str = ""  # HTML table content
    table_caption: list[str] = field(default_factory=list)
    table_footnote: list[str] = field(default_factory=list)

    # equation fields
    text_format: str = ""  # "latex" for equations

    # code fields
    code_body: str = ""
    code_caption: list[str] = field(default_factory=list)
    code_sub_type: str = ""  # "code" or "algorithm"

    # list fields
    list_sub_type: str = ""  # "text" or "ref_text"
    list_items: list[str] = field(default_factory=list)

    # chart fields
    chart_caption: list[str] = field(default_factory=list)
    chart_footnote: list[str] = field(default_factory=list)

    # header/footer/page_number/aside_text/page_footnote
    # uses `text` field above

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MinerU content_list.json compatible format."""
        d: dict[str, Any] = {
            "type": self.type,
            "page_idx": self.page_idx,
        }
        if self.bbox:
            d["bbox"] = self.bbox

        if self.type in ("text", "title"):
            d["text"] = self.text
            if self.text_level is not None:
                d["text_level"] = self.text_level
        elif self.type == "image":
            if self.img_path:
                d["img_path"] = self.img_path
            if self.content:
                d["content"] = self.content
            d["image_caption"] = self.image_caption
            d["image_footnote"] = self.image_footnote
            if self.sub_type:
                d["sub_type"] = self.sub_type
        elif self.type == "table":
            if self.img_path:
                d["img_path"] = self.img_path
            d["table_body"] = self.table_body
            d["table_caption"] = self.table_caption
            d["table_footnote"] = self.table_footnote
        elif self.type == "equation":
            d["text"] = self.text
            d["text_format"] = self.text_format
        elif self.type in ("chart",):
            if self.img_path:
                d["img_path"] = self.img_path
            if self.content:
                d["content"] = self.content
            d["chart_caption"] = self.chart_caption
            d["chart_footnote"] = self.chart_footnote
            if self.sub_type:
                d["sub_type"] = self.sub_type
        elif self.type == "code":
            d["code_body"] = self.code_body
            d["code_caption"] = self.code_caption
            if self.code_sub_type:
                d["sub_type"] = self.code_sub_type
        elif self.type == "list":
            d["sub_type"] = self.list_sub_type
            d["list_items"] = self.list_items
        elif self.type in ("header", "footer", "page_number", "aside_text", "page_footnote"):
            d["text"] = self.text

        return d

    @classmethod
    def from_mineru_block(cls, block: dict[str, Any]) -> ContentBlock:
        """Create from a MinerU content_list.json block dict."""
        block_type = block.get("type", "text")
        return cls(
            type=block_type,
            page_idx=block.get("page_idx", 0),
            bbox=block.get("bbox", []),
            text=block.get("text", ""),
            text_level=block.get("text_level"),
            img_path=block.get("img_path", ""),
            content=block.get("content", ""),
            image_caption=block.get("image_caption", []),
            image_footnote=block.get("image_footnote", []),
            sub_type=block.get("sub_type", ""),
            table_body=block.get("table_body", ""),
            table_caption=block.get("table_caption", []),
            table_footnote=block.get("table_footnote", []),
            text_format=block.get("text_format", ""),
            code_body=block.get("code_body", ""),
            code_caption=block.get("code_caption", []),
            code_sub_type=block.get("sub_type", "") if block_type == "code" else "",
            list_sub_type=block.get("sub_type", "") if block_type == "list" else "",
            list_items=block.get("list_items", []),
            chart_caption=block.get("chart_caption", []),
            chart_footnote=block.get("chart_footnote", []),
        )
```

**Step 2: Add `original_blocks` to FormattedDocument**

```python
@dataclass
class FormattedDocument:
    # ... existing fields ...
    original_blocks: List[ContentBlock] = field(default_factory=list)
```

**Step 3: Add `translated_blocks` to TranslationResult**

```python
@dataclass
class TranslationResult:
    # ... existing fields ...
    original_blocks: List[ContentBlock] = field(default_factory=list)
    translated_blocks: List[ContentBlock] = field(default_factory=list)
```

**Step 4: Run tests to verify no regressions**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py
git commit -m "feat: add ContentBlock contract for structured JSON persistence"
```

---

### Task 2: Preserve MinerU Blocks in Parser

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`

**Step 1: Add `content_blocks` field to ParseResult**

In `parse_document/contracts.py`, add to `ParseResult`:

```python
class ParseResult(BaseModel):
    # ... existing fields ...
    content_blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw MinerU content_list blocks for structured persistence",
    )
```

**Step 2: Store raw content_list blocks in `_parse_content_list_json`**

In `mineru_parser.py`, modify `_parse_content_list_json` to preserve the raw blocks:

```python
def _parse_content_list_json(self, content_list: list[dict], full_markdown: str) -> _MinerURawResult:
    # ... existing code ...
    # Add raw_blocks to the return
    result["raw_blocks"] = [b for b in content_list if b.get("type") != "discarded"]
    return result
```

And update `_MinerURawResult` to include `raw_blocks`:

```python
class _MinerURawResult(TypedDict):
    state: str
    total_pages: int
    title: str | None
    authors: list[str]
    abstract: str | None
    pages: list[_MinerUPageData]
    full_markdown: str
    images: dict[str, bytes]
    raw_blocks: list[dict]  # NEW
```

Update all return sites in `_parse_extracted_content` to include `raw_blocks: []`.

**Step 3: Pass raw_blocks through _build_result**

```python
def _build_result(self, data: _MinerURawResult) -> ParseResult:
    # ... existing code ...
    return ParseResult(
        # ... existing fields ...
        content_blocks=data.get("raw_blocks", []),
    )
```

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/ -v
```

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py
git commit -m "feat: preserve MinerU content_list blocks in ParseResult"
```

---

### Task 3: Thread Blocks Through Formatter

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py`

**Step 1: Pass blocks through formatter**

In `formatter.py`, update `_format_markdown` to accept and forward blocks:

```python
def _format_markdown(
    pages: List[Dict[str, Any]],
    raw_markdown: str = "",
    content_blocks: List[Dict[str, Any]] | None = None,
) -> FormattedDocument:
    # ... existing code ...
    from ...contracts import ContentBlock
    blocks = [ContentBlock.from_mineru_block(b) for b in (content_blocks or [])]

    return FormattedDocument(
        formatted_markdown=formatted,
        sentences=sentences,
        metadata={"page_count": len(pages)},
        raw_markdown=raw_copy,
        original_blocks=blocks,
    )
```

Update `MarkdownFormatter.format` signature similarly.

**Step 2: Pass blocks from workflow to formatter**

In `workflow.py`, the `format_node` function receives `PipelineState`. Update it to pass `content_blocks` from the state's pages or a dedicated field.

The simplest approach: add `content_blocks` to `PipelineState`:

```python
class PipelineState(BaseModel):
    # ... existing fields ...
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)
```

In the workflow's entry point, populate `content_blocks` from `ParseResult.content_blocks`.

**Step 3: Run tests**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py
git add backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py
git add backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py
git commit -m "feat: thread MinerU blocks through formatter into FormattedDocument"
```

---

### Task 4: Produce Translated Blocks in Translator

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py`

**Step 1: After translation, map translated text back to blocks**

In `MultiStageTranslator.run_pipeline()`, after joining translated segments into `final_translated`, produce `translated_blocks`:

```python
def _build_translated_blocks(
    original_blocks: list[ContentBlock],
    translated_text: str,
    segments: list[TranslationSegment],
) -> list[ContentBlock]:
    """Map translated text back to original block structure.

    Strategy: For text/title blocks, use segment alignment to find the
    translated content. For non-text blocks (image, table, etc.),
    copy the original block as-is (captions stay in source language,
    or can be translated separately later).
    """
    # Build a source→translated mapping from segments
    # Each segment covers a range of the source text
    # ... implementation ...

    translated_blocks = []
    for block in original_blocks:
        if block.type in ("text", "title"):
            # Find which segments overlap this block's text
            # Concatenate their translations
            new_block = ContentBlock(
                type=block.type,
                page_idx=block.page_idx,
                bbox=block.bbox,
                text=find_translated_text_for_block(block, segments, translated_text),
                text_level=block.text_level,
            )
        else:
            # Non-text blocks: copy as-is
            new_block = ContentBlock(
                type=block.type,
                page_idx=block.page_idx,
                bbox=block.bbox,
                # ... copy all fields from block ...
            )
        translated_blocks.append(new_block)
    return translated_blocks
```

The key helper `find_translated_text_for_block` uses the segment source_text to find which segments cover this block, then returns the concatenated translated_text of those segments.

**Step 2: Set translated_blocks on TranslationResult**

In `run_pipeline`, after building `TranslationResult`, add:

```python
translated_blocks = _build_translated_blocks(
    formatted.original_blocks, final_translated, result.segments,
)
result = TranslationResult(
    # ... existing fields ...
    original_blocks=formatted.original_blocks,
    translated_blocks=translated_blocks,
)
```

**Step 3: Run tests**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

**Step 4: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py
git commit -m "feat: produce translated blocks by mapping translation back to block structure"
```

---

### Task 5: Rewrite Persistence to Save Structured JSON

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py`

**Step 1: Update SavedDocuments contract**

```python
@dataclass
class SavedDocuments:
    """Result of persisting cross-lingual documents to storage."""

    original_json_path: Path       # was original_md_path
    translated_json_path: Path     # was translated_md_path
    metadata_path: Path
    image_dir: Path
    image_paths: list[Path]
    output_dir: Path
    created_at: datetime
```

Update `CrossLingualOutput` similarly — replace `original_md_path`/`translated_md_path` with `original_json_path`/`translated_json_path`.

**Step 2: Rewrite `save()` method**

Replace markdown file writes with JSON:

```python
def save(self, result, output_dir, doc_id, image_paths=None, raw_markdown=""):
    base = Path(output_dir) / doc_id
    base.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    # Save original.json (structured blocks)
    original_path = base / "original.json"
    original_data = {
        "metadata": {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "block_count": len(result.original_blocks),
        },
        "blocks": [b.to_dict() for b in result.original_blocks],
    }
    original_path.write_text(
        json.dumps(original_data, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Save translated.json (structured blocks with translations)
    translated_path = base / "translated.json"
    translated_data = {
        "metadata": {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "block_count": len(result.translated_blocks),
            "terminology_map": result.terminology_map,
            "translation_warnings": result.translation_warnings,
        },
        "blocks": [b.to_dict() for b in result.translated_blocks],
    }
    translated_path.write_text(
        json.dumps(translated_data, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Save metadata.json (enhanced with drift info from old layout JSONs)
    metadata = {
        "doc_id": doc_id,
        "source_language": result.source_language,
        "terminology_map": result.terminology_map,
        "translation_warnings": result.translation_warnings,
        "sentence_count": len(result.sentences),
        "segment_count": len(result.segments),
        "original_block_count": len(result.original_blocks),
        "translated_block_count": len(result.translated_blocks),
        "created_at": now.isoformat(),
    }
    meta_path = base / "metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # ... image copying unchanged ...

    return SavedDocuments(
        original_json_path=original_path,
        translated_json_path=translated_path,
        metadata_path=meta_path,
        image_dir=image_dir,
        image_paths=saved_image_paths,
        output_dir=base,
        created_at=now,
    )
```

**Step 3: Remove `_save_original_layout` and `_save_translated_layout` methods**

These are no longer needed — drift info is folded into metadata.json.

**Step 4: Update `to_output()` to use new path names**

```python
@staticmethod
def to_output(result, saved):
    return CrossLingualOutput(
        # ... other fields ...
        original_json_path=str(saved.original_json_path),
        translated_json_path=str(saved.translated_json_path),
    )
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/persistence.py
git add backend/src/core/cross_lingual_process_and_extract_evidence/contracts.py
git commit -m "feat: replace .md persistence with structured JSON (original.json, translated.json)"
```

---

### Task 6: Update E2E Script and Tests

**Files:**
- Modify: `backend/scripts/e2e_full.py`
- Modify: `backend/tests/core/cross_lingual_process_and_extract_evidence/test_integration.py`

**Step 1: Update e2e_full.py**

Pass `content_blocks` from parse result through to the translation pipeline. Update `parse_one` to return `content_blocks`. Update `translate_and_save` to pass them to the service.

**Step 2: Update test assertions**

Replace assertions on `original.md` / `translated.md` existence with assertions on `original.json` / `translated.json`. Verify JSON structure has `blocks` array with proper `type`/`page_idx` fields.

**Step 3: Run full test suite**

```bash
cd backend && uv run pytest tests/ -v
```

**Step 4: Run e2e test**

```bash
cd backend && uv run python scripts/e2e_full.py downloads/zh/法布雷病1例.pdf
```

Verify output contains `original.json` and `translated.json` with proper block structure.

**Step 5: Commit**

```bash
git add backend/scripts/e2e_full.py
git add backend/tests/
git commit -m "test: update e2e script and tests for structured JSON persistence"
```

---

### Task 7: Cleanup and Documentation

**Files:**
- Remove: old `original_layout.json` / `translated_layout.json` generation code (already done in Task 5)
- Modify: `progress.txt`
- Modify: `docs/` if needed

**Step 1: Verify no references to removed .md paths**

```bash
cd backend && grep -r "original_md_path\|translated_md_path\|original\.md\|translated\.md" src/ --include="*.py"
```

Update any remaining references.

**Step 2: Update progress.txt**

```
[2026-05-17] Replace .md persistence with structured JSON (original.json, translated.json) [DONE]
```

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: cleanup references to removed .md persistence files"
```

---

## JSON Output Schema

### original.json
```json
{
  "metadata": {
    "doc_id": "法布雷病1例",
    "source_language": "zh",
    "block_count": 42
  },
  "blocks": [
    {
      "type": "title",
      "text": "法布雷病1例",
      "text_level": 1,
      "bbox": [62, 48, 946, 112],
      "page_idx": 0
    },
    {
      "type": "text",
      "text": "张虹 蒋钻红 邵松华",
      "bbox": [62, 120, 946, 155],
      "page_idx": 0
    },
    {
      "type": "image",
      "img_path": "images/10694e448f.jpg",
      "image_caption": ["图1 法布雷病患者基因检测"],
      "image_footnote": [],
      "bbox": [100, 300, 900, 600],
      "page_idx": 1
    },
    {
      "type": "table",
      "table_body": "<table>...</table>",
      "table_caption": ["表1 患者酶替代疗法治疗前后实验室及心脏超声检查结果"],
      "table_footnote": ["注：肌钙蛋白Ⅰ正常参考值..."],
      "bbox": [62, 200, 946, 500],
      "page_idx": 2
    }
  ]
}
```

### translated.json
```json
{
  "metadata": {
    "doc_id": "法布雷病1例",
    "source_language": "zh",
    "block_count": 42,
    "terminology_map": {},
    "translation_warnings": []
  },
  "blocks": [
    {
      "type": "title",
      "text": "A Case of Fabry Disease",
      "text_level": 1,
      "bbox": [62, 48, 946, 112],
      "page_idx": 0
    },
    {
      "type": "text",
      "text": "Zhang Hong, Jiang Zuanhong, Shao Songhua",
      "bbox": [62, 120, 946, 155],
      "page_idx": 0
    },
    {
      "type": "image",
      "img_path": "images/10694e448f.jpg",
      "image_caption": ["Figure 1 Gene detection in Fabry disease patient"],
      "image_footnote": [],
      "bbox": [100, 300, 900, 600],
      "page_idx": 1
    }
  ]
}
```

### metadata.json (enhanced)
```json
{
  "doc_id": "法布雷病1例",
  "source_language": "zh",
  "terminology_map": {},
  "translation_warnings": [],
  "sentence_count": 110,
  "segment_count": 2,
  "original_block_count": 42,
  "translated_block_count": 42,
  "created_at": "2026-05-17T01:59:56Z"
}
```

---

## Risk Mitigation

1. **Translation quality**: The LLM translation pipeline stays unchanged — we still translate the full markdown for quality. Block mapping is a post-processing step.

2. **Block alignment**: If a translated segment doesn't cleanly map to a single block (e.g., a segment spans multiple blocks), the helper function concatenates translations from overlapping segments. This is a best-effort mapping.

3. **Non-text blocks**: Images, tables, equations are copied as-is from original blocks. Captions can be translated in a future enhancement.

4. **Backward compatibility**: `CrossLingualOutput` field names change. Any downstream consumers need updating. Check with `grep -r "original_md_path\|translated_md_path" backend/src/`.
