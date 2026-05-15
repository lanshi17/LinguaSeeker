# Parse Document Image Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract and persist images from MinerU-parsed documents so downstream phases can use figure content for evidence extraction.

**Architecture:** MinerU API returns a zip containing `images/` directory with extracted figures. Currently the parser discards these images. We extend `FigurePosition` with `img_path`, collect image bytes during zip parsing, carry them through `ParseResult`, and persist them in `service.save()`.

**Tech Stack:** Python, Pydantic, pytest, tempfile, zipfile

---

## Task 1: Extend `FigurePosition` contract with `img_path`

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py:23-28`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py:39-47`

**Step 1: Write the failing test**

```python
# In test_contracts.py, add to TestFigurePosition class:

def test_figure_with_img_path(self):
    fig = FigurePosition(page=1, index=1, caption="Fig 1", img_path="images/fig1.jpg")
    assert fig.img_path == "images/fig1.jpg"

def test_figure_img_path_default_none(self):
    fig = FigurePosition(page=1, index=1)
    assert fig.img_path is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py::TestFigurePosition::test_figure_with_img_path -v`
Expected: FAIL with `ValidationError` or `AttributeError`

**Step 3: Write minimal implementation**

```python
# In contracts.py, FigurePosition class (line 23-28):

class FigurePosition(BaseModel):
    """Position of a figure within the document."""

    page: int = Field(ge=1)
    index: int = Field(ge=1, description="Figure index on this page")
    caption: str | None = None
    img_path: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py::TestFigurePosition -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py
git commit -m "feat: add img_path field to FigurePosition contract"
```

---

## Task 2: Add `images` field to `ParseResult`

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py:91-106`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`

**Step 1: Write the failing test**

```python
# In test_contracts.py, add to TestParseResult class:

def test_result_with_images(self):
    result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="Content")],
        images={"images/fig1.jpg": b"\xff\xd8\xff\xe0", "images/fig2.png": b"\x89PNG"},
    )
    assert len(result.images) == 2
    assert b"\xff\xd8" in result.images["images/fig1.jpg"]

def test_result_images_default_empty(self):
    result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="Content")],
    )
    assert result.images == {}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py::TestParseResult::test_result_with_images -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# In contracts.py, ParseResult class (line 91-106):

class ParseResult(BaseModel):
    """Complete result of PDF parsing.

    ``full_markdown`` is automatically derived from ``pages`` if not provided.
    """

    metadata: DocumentMetadata
    pages: list[PageContent]
    full_markdown: str = ""
    parser_used: ParserName = "unknown"
    images: dict[str, bytes] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_full_markdown(self) -> ParseResult:
        if not self.full_markdown and self.pages:
            self.full_markdown = "\n\n".join(p.markdown for p in self.pages)
        return self
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py::TestParseResult -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py
git commit -m "feat: add images dict to ParseResult for image bytes storage"
```

---

## Task 3: Extract `img_path` and image bytes in MinerU parser

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py:27-42, 150-163, 281-338, 340-354`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the failing test**

```python
# In test_mineru_parser.py, add:

def test_parse_extracted_content_collects_images(self, parser):
    """Verify parser collects image files from zip."""
    with tempfile.TemporaryDirectory() as tmp:
        content_dir = Path(tmp) / "extract"
        content_dir.mkdir()

        # Create images directory with a fake image
        images_dir = content_dir / "images"
        images_dir.mkdir()
        fake_jpg = b"\xff\xd8\xff\xe0\x00fake_jpg_data"
        (images_dir / "fig1.jpg").write_bytes(fake_jpg)

        # full.md
        (content_dir / "full.md").write_text("# Title", encoding="utf-8")

        # content_list.json with image block
        content_list = [
            {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
            {
                "type": "image",
                "img_path": "images/fig1.jpg",
                "image_caption": ["Figure 1"],
                "page_idx": 0,
            },
        ]
        (content_dir / "test_content_list.json").write_text(
            json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
        )

        result = parser._parse_extracted_content(content_dir)

    assert result["state"] == "done"
    assert len(result["images"]) == 1
    assert "images/fig1.jpg" in result["images"]
    assert result["images"]["images/fig1.jpg"] == fake_jpg


def test_parse_extracted_content_figure_has_img_path(self, parser):
    """Verify figure data includes img_path."""
    with tempfile.TemporaryDirectory() as tmp:
        content_dir = Path(tmp) / "extract"
        content_dir.mkdir()
        (content_dir / "full.md").write_text("text", encoding="utf-8")

        content_list = [
            {
                "type": "image",
                "img_path": "images/fig1.jpg",
                "image_caption": ["Figure 1"],
                "page_idx": 0,
            },
        ]
        (content_dir / "test_content_list.json").write_text(
            json.dumps(content_list), encoding="utf-8"
        )

        result = parser._parse_extracted_content(content_dir)

    page = result["pages"][0]
    assert page["figures"][0]["img_path"] == "images/fig1.jpg"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_parse_extracted_content_collects_images tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_parse_extracted_content_figure_has_img_path -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Changes to `mineru_parser.py`:

1. Add `images` field to `_MinerURawResult`:
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
```

2. Add `img_path` to `_MinerUPageData` figures entries (already dict, just add key in `_parse_content_list_json`)

3. In `_parse_content_list_json` (line 313-315), extract `img_path`:
```python
if block_type == "image":
    caption = block.get("image_caption", [])
    img_path = block.get("img_path")  # None when key is missing, consistent with FigurePosition default
    figures.append({
        "index": len(figures) + 1,
        "caption": str(caption[0]) if caption else "",
        "img_path": img_path,
    })
```

4. Add `_collect_images` helper method:
```python
def _collect_images(self, extract_dir: Path) -> dict[str, bytes]:
    """Collect image files from extracted zip directory."""
    images: dict[str, bytes] = {}
    images_dir = extract_dir / "images"
    if images_dir.is_dir():
        for img_file in images_dir.iterdir():
            if img_file.is_file():
                rel_path = f"images/{img_file.name}"
                images[rel_path] = img_file.read_bytes()
    return images
```

5. Update `_parse_extracted_content` to collect images once and merge into whichever format path wins. Instead of sprinkling `images=self._collect_images(extract_dir)` across 4 separate return statements, collect once at the top and merge into the result before returning:

```python
# In _parse_extracted_content, collect images once, merge at return point:
images = self._collect_images(extract_dir)

# ... existing format detection logic ...

# Priority 1: content_list.json
if content_list_files:
    try:
        data = json.loads(content_list_files[0].read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            result = self._parse_content_list_json(data, full_markdown)
            result["images"] = images
            return result
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

# Priority 2: layout.json
for jf in json_files:
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
        result: _MinerURawResult
        if isinstance(data, dict) and "pdf_info" in data:
            result = self._parse_content_json(data, md_files)
        elif isinstance(data, list) and len(data) > 0:
            result = self._parse_content_json({"pages": data}, md_files)
        else:
            continue
        result["images"] = images
        return result
    except (json.JSONDecodeError, UnicodeDecodeError):
        continue

# Priority 3: markdown files
if md_files:
    result = self._parse_markdown_files(md_files)
    result["images"] = images
    return result

# Priority 4: full.md only
if full_markdown:
    return _MinerURawResult(
        state="done",
        total_pages=1,
        title=None,
        authors=[],
        abstract=None,
        pages=[_MinerUPageData(page_number=1, markdown=full_markdown, figures=[], tables=[])],
        full_markdown=full_markdown,
        images=images,
    )
```

This is cleaner and prevents silently losing images when a 5th format path is added later.

6. Update `_build_result` to pass images through:
```python
return ParseResult(
    ...,
    images=data.get("images", {}),
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py -v`
Expected: PASS (all existing + new tests)

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat: extract image files and img_path from MinerU zip output"
```

---

## Task 4: Update `service.save()` to persist images

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py:109-116` (SavedFiles)
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py:37-63`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py`

**Step 1: Write the failing test**

```python
# In test_service.py, add:


from unittest.mock import AsyncMock, patch

# Standalone functions (no class needed — save() doesn't use orchestrator):

@pytest.mark.asyncio
async def test_save_persists_images(tmp_path):
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        DocumentMetadata, PageContent, ParseResult,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService

    service = ParseDocumentService(orchestrator=AsyncMock())  # orchestrator not needed for save

    result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="Content")],
        images={"images/fig1.jpg": b"\xff\xd8\xff\xe0"},
    )

    saved = await service.save(result, str(tmp_path))

    assert saved.images_dir is not None
    assert (saved.images_dir / "fig1.jpg").exists()
    assert (saved.images_dir / "fig1.jpg").read_bytes() == b"\xff\xd8\xff\xe0"


@pytest.mark.asyncio
async def test_save_no_images(tmp_path):
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        DocumentMetadata, PageContent, ParseResult,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService

    service = ParseDocumentService(orchestrator=AsyncMock())

    result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="Content")],
    )

    saved = await service.save(result, str(tmp_path))

    assert saved.images_dir is None
```


# Inside TestParseDocumentService class (needs self.mock_orchestrator fixture):


@pytest.mark.asyncio
async def test_parse_and_save_preserves_images(self, mock_orchestrator, tmp_path):
    """Verify parse_and_save carries images through to ParseAndSaveResult."""
    output_dir = str(tmp_path / "output")

    parse_result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="Content")],
        parser_used="mineru-remote",
        images={"images/fig1.jpg": b"\xff\xd8\xff\xe0"},
    )
    mock_orchestrator.parse.return_value = parse_result
    service = ParseDocumentService(orchestrator=mock_orchestrator)

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
        result = await service.parse_and_save(
            "https://example.com/test.pdf", output_dir
        )

    assert len(result.images) == 1
    assert b"\xff\xd8" in result.images["images/fig1.jpg"]
    assert result.saved_files is not None
    assert result.saved_files.images_dir is not None

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py::test_save_persists_images tests/core/ingest_and_digitize_data/parse_document/test_service.py::test_parse_and_save_preserves_images -v`
Expected: FAIL

**Step 3: Write minimal implementation**

1. Update `SavedFiles` in `contracts.py`:
```python
@dataclass
class SavedFiles:
    """Result of saving parsed document to files."""

    md_path: Path
    metadata_path: Path
    output_dir: Path
    created_at: datetime
    images_dir: Path | None = None
```

2. Update `service.save()`:
```python
async def save(self, result: ParseResult, output_dir: str) -> SavedFiles:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    md_path = output_path / "output.md"
    files_io.File(str(md_path)).write(result.full_markdown)

    meta_path = output_path / "metadata.json"
    files_io.File(str(meta_path)).write(json.dumps(result.metadata.model_dump(), indent=2))

    images_dir: Path | None = None
    if result.images:
        images_dir = output_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, img_bytes in result.images.items():
            img_file = images_dir / Path(rel_path).name
            img_file.write_bytes(img_bytes)
        logger.info(f"Saved {len(result.images)} images to {images_dir}")

    return SavedFiles(
        md_path=md_path,
        metadata_path=meta_path,
        output_dir=output_path,
        created_at=datetime.now(timezone.utc),
        images_dir=images_dir,
    )
```

> **Note:** `Path(rel_path).name` strips subdirectory prefixes (e.g. `images/sub/a.jpg` → `a.jpg`). If MinerU ever produces nested image directories with same-named files, they would collide. Currently MinerU uses flat `images/` with unique filenames, so this is fine.


3. Update `service.parse_and_save()` to pass `images` through:
```python
async def parse_and_save(
    self,
    pdf_path: str,
    output_dir: str,
) -> ParseAndSaveResult:
    parse_result = await self.parse(pdf_path)
    saved_files = await self.save(parse_result, output_dir)

    return ParseAndSaveResult(
        metadata=parse_result.metadata,
        pages=parse_result.pages,
        full_markdown=parse_result.full_markdown,
        parser_used=parse_result.parser_used,
        images=parse_result.images,
        saved_files=saved_files,
    )
```

> **Note:** Without this, `parse_and_save()` silently drops `images` — the caller receives `images={}` even though images were saved to disk.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
       backend/src/core/ingest_and_digitize_data/parse_document/service.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py
git commit -m "feat: persist extracted images in service.save() and parse_and_save()"
```

---

## Task 5: Update `_figures_from_page` to propagate `img_path`

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py:54-59`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`

**Step 1: Write the failing test**

```python
# In test_contracts.py, add:

def test_pages_from_raw_with_img_path(self):
    from src.core.ingest_and_digitize_data.parse_document.contracts import pages_from_raw

    pages_data = [
        {
            "page_number": 1,
            "markdown": "text",
            "figures": [{"index": 1, "caption": "Fig 1", "img_path": "images/fig1.jpg"}],
            "tables": [],
        },
    ]
    pages = pages_from_raw(pages_data)
    assert pages[0].figures[0].img_path == "images/fig1.jpg"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py::test_pages_from_raw_with_img_path -v`
Expected: FAIL (img_path not passed through)

**Step 3: Write minimal implementation**

```python
# In contracts.py, _figures_from_page (line 54-59):

def _figures_from_page(page_number: int, figures: list[dict]) -> list[FigurePosition]:
    """Extract figure positions from raw page data."""
    return [
        FigurePosition(
            page=page_number,
            index=f.get("index", 1),
            caption=f.get("caption"),
            img_path=f.get("img_path"),
        )
        for f in figures
    ]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py -v`
Expected: PASS


**Step 4b: Add cross-cutting integration test** — verify the full pipe from `_build_result` to `FigurePosition.img_path`:

```python
# In test_mineru_parser.py, add to TestMinerUParser:

def test_build_result_propagates_img_path(self, parser):
    """Verify _build_result correctly maps img_path through to FigurePosition."""
    raw = {
        "state": "done",
        "total_pages": 1,
        "title": None,
        "authors": [],
        "abstract": None,
        "pages": [
            {
                "page_number": 1,
                "markdown": "text",
                "figures": [
                    {"index": 1, "caption": "Fig 1", "img_path": "images/fig1.jpg"}
                ],
                "tables": [],
            }
        ],
        "full_markdown": "text",
        "images": {"images/fig1.jpg": b"\xff\xd8"},
    }
    result = parser._build_result(raw)

    assert result.pages[0].figures[0].img_path == "images/fig1.jpg"
    assert len(result.images) == 1
```

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_build_result_propagates_img_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py \
       backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat: propagate img_path through _figures_from_page to ParseResult"
```

---

## Task 6: Update `__init__.py` exports and run full test suite

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py` (if needed)

**Step 1: Verify exports are correct**

Check that `FigurePosition` (with new `img_path`) and `ParseResult` (with new `images`) are already exported in `__init__.py`. They should be — both were already in `__all__`.



**Step 1b: Verify downstream callers still work**

Run these tests to confirm that callers unaffected by the `images` default still pass:
- `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_contracts.py -v` — `test_parse_and_save_result_creation` creates `ParseAndSaveResult` without `images`; should pass with default `{}`.
- `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_local_parser.py -v` — `MinerULocalParser.parse()` creates `ParseResult` without `images`; the VLM path intentionally produces `images={}` since it gets markdown, not image files.
- `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_new_service.py -v` — `test_service_parse_and_save` creates `ParseAndSaveResult` without `images`; should pass.
Expected: ALL PASS
**Step 2: Run full test suite**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v`
Expected: ALL PASS

**Step 3: Run linter**

Run: `cd backend && uv run ruff check src/core/ingest_and_digitize_data/parse_document/`
Expected: No errors

**Step 4: Commit (if any fixups needed)**

```bash
git add -A
git commit -m "chore: verify image extraction integration across parse_document module"
```

---

## Verification: `block_to_markdown` image path handling

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/common/converters.py:56-68`

**Step 1: Write the failing test**

```python
# In test_common.py, add:

def test_block_to_markdown_image_without_path():
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {
        "type": "image",
        "img_path": "",
        "image_caption": ["Figure 1: Caption only"],
    }
    result = block_to_markdown(block)
    assert "Figure 1: Caption only" in result
    assert "![" not in result  # no img reference when path is empty
```

**Step 2: Run test to verify current behavior**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_common.py::test_block_to_markdown_image_without_path -v`
Expected: PASS (current code already handles empty img_path correctly — `if img_path:` check at line 62)

**Step 3: No change needed — verify existing behavior is correct**

The current `block_to_markdown` already handles the image block correctly:
- If `img_path` is non-empty: generates `![caption](img_path)`
- If `img_path` is empty but caption exists: outputs caption text only

This is correct behavior. The markdown references use the zip-internal path, which is fine for provenance. The actual image bytes are carried separately in `ParseResult.images`.

**Step 4: Skip commit — no changes needed**
