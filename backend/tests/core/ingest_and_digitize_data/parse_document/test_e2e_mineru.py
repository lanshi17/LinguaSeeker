"""End-to-end tests for MinerU API and Local parsers.

Tests both parsing modes against real PDFs in backend/downloads/:

- **Local mode**: MinerULocalParser → model-server VLM endpoint (port 8001)
- **API mode**: upload local PDF via MinerU cloud API → poll batch result → parse

Requires:
- model-server running on localhost:8001 (for local mode)
- MINERU_API_TOKEN env var set (for API mode)
- rust_io.net PyO3 extension built

Output saved to /tmp/e2e_output/{lang}/{pdf_stem}/{mode}/
"""
from __future__ import annotations

import asyncio
import json
import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from loguru import logger

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.mineru_local_parser import (
    MinerULocalParser,
)
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import (
    MinerUParser,
)

DOWNLOADS_DIR = Path(__file__).resolve().parents[4] / "downloads"
OUTPUT_DIR = Path("/tmp/e2e_output")


# ── Helpers ─────────────────────────────────────────────────────────────


def _collect_pdfs() -> list[tuple[str, str]]:
    """Collect all PDFs from downloads/ excluding v1.1/, returning (path, lang)."""
    pdfs = []
    for lang_dir in sorted(DOWNLOADS_DIR.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name == "v1.1":
            continue
        lang = lang_dir.name
        for pdf in sorted(lang_dir.glob("*.pdf")):
            pdfs.append((str(pdf), lang))
    return pdfs


def _save_output(lang: str, pdf_path: str, mode: str, result: ParseResult) -> Path:
    """Save parse result to /tmp/e2e_output/{lang}/{pdf_stem}/{mode}/."""
    pdf_stem = Path(pdf_path).stem
    out_dir = OUTPUT_DIR / lang / pdf_stem / mode
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "output.md"
    md_path.write_text(result.full_markdown, encoding="utf-8")

    meta_path = out_dir / "metadata.json"
    meta_path.write_text(
        json.dumps(result.metadata.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Per-page output
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    for page in result.pages:
        page_path = pages_dir / f"page_{page.page_number:03d}.md"
        page_path.write_text(page.markdown, encoding="utf-8")

    return out_dir


def _assert_parse_result(result: ParseResult, pdf_path: str) -> None:
    """Validate a ParseResult has sensible content."""
    assert isinstance(result, ParseResult)
    assert result.metadata.total_pages >= 1
    assert len(result.pages) >= 1
    assert result.full_markdown, f"Empty markdown for {pdf_path}"
    assert result.parser_used == "mineru"

    for page in result.pages:
        assert page.page_number >= 1


async def _upload_and_parse_api(
    pdf_path: str,
    token: str,
    poll_interval: float = 3.0,
    max_poll_attempts: int = 100,
) -> ParseResult:
    """Upload local PDF via MinerU cloud API, poll batch result, and parse.

    Flow:
    1. Upload PDF via mineru_upload_local_files -> get batch_id
    2. Poll mineru_batch_result until state=done
    3. Download and parse zip from result
    """
    import rust_io.net as net_io

    pdf_name = Path(pdf_path).name
    logger.info(f"API mode: uploading {pdf_name}")

    # Step 1: upload
    upload_response = await net_io.mineru_upload_local_files(
        file_paths=[pdf_path],
        token=token,
        enable_formula=True,
        enable_table=True,
    )

    # Extract batch_id
    batch_id = None
    if isinstance(upload_response, dict):
        data = upload_response.get("data", {})
        if isinstance(data, dict):
            batch_id = data.get("batch_id")
    if not batch_id:
        raise MinerUAPIError(f"No batch_id in upload response: {upload_response}")

    logger.info(f"API mode: batch_id={batch_id}, polling...")

    # Step 2: poll batch result
    # MinerU batch response has extract_result[] with per-file states.
    # Top-level data.state may not exist; check extract_result[0].state instead.
    for attempt in range(max_poll_attempts):
        batch_resp = await net_io.mineru_batch_result(
            batch_id=batch_id,
            token=token,
        )

        if not isinstance(batch_resp, dict):
            raise MinerUAPIError(f"Invalid batch response: {batch_resp}")

        data = batch_resp.get("data", {})
        if not isinstance(data, dict):
            raise MinerUAPIError(f"Invalid batch data: {batch_resp}")

        # Check per-file state in extract_result
        extract_results = data.get("extract_result", [])
        if extract_results and isinstance(extract_results, list):
            file_result = extract_results[0]
            file_state = file_result.get("state", "")

            if file_state == "done":
                logger.info(f"API mode: batch done after {attempt + 1} polls")
                return _parse_batch_done_response(data, pdf_path)
            elif file_state == "failed":
                err_msg = file_result.get("err_msg", "Unknown")
                raise MinerUAPIError(f"Batch file failed: {err_msg}")
            elif file_state in ("waiting-file", "pending", "running", "converting", "ready"):
                logger.debug(f"Batch file state: {file_state}, waiting...")
                await asyncio.sleep(poll_interval)
            else:
                raise MinerUAPIError(f"Unknown batch file state: {file_state}")
        else:
            # Fallback: check top-level state
            state = data.get("state", "")
            if state == "done":
                logger.info(f"API mode: batch done after {attempt + 1} polls")
                return _parse_batch_done_response(data, pdf_path)
            elif state == "failed":
                raise MinerUAPIError(f"Batch failed: {data.get('err_msg', 'Unknown')}")
            elif state in ("pending", "running", "converting"):
                logger.debug(f"Batch state: {state}, waiting...")
                await asyncio.sleep(poll_interval)
            elif not state:
                # No state yet, keep polling
                logger.debug("No state in batch response, waiting...")
                await asyncio.sleep(poll_interval)
            else:
                raise MinerUAPIError(f"Unknown batch state: {state}")

    raise MinerUAPIError(f"Batch polling timeout after {max_poll_attempts} attempts")


def _parse_batch_done_response(data: dict, pdf_path: str) -> ParseResult:
    """Parse a completed batch response into ParseResult."""
    # Response format: data.extract_result[0].full_zip_url
    extract_results = data.get("extract_result", [])
    zip_url = None
    if isinstance(extract_results, list) and extract_results:
        zip_url = extract_results[0].get("full_zip_url")
    if not zip_url:
        zip_url = data.get("full_zip_url")
    if not zip_url:
        zip_url = data.get("zip_url")
    if not zip_url:
        raise MinerUAPIError(f"No zip URL in batch done response. Keys: {list(data.keys())}")

    logger.info("API mode: downloading result zip")

    # Download and parse zip synchronously (small file)
    resp = httpx.get(zip_url, timeout=120.0)
    resp.raise_for_status()

    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        # Extract to temp and parse
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            zf.extractall(tmp_dir)
            return _parse_zip_content(Path(tmp_dir))


def _parse_zip_content(extract_dir: Path) -> ParseResult:
    """Parse MinerU zip content into ParseResult.

    MinerU zip structure:
    - full.md: complete markdown
    - *_content_list.json: flat list of content blocks with page_idx
    - layout.json: pdf_info with page structure (may have empty page_content)
    - images/: extracted images
    """
    # 1. Try full.md as primary markdown source
    full_md_path = extract_dir / "full.md"
    full_markdown = ""
    if full_md_path.exists():
        full_markdown = full_md_path.read_text(encoding="utf-8")

    # 2. Try *_content_list.json for per-page content
    content_list_files = [f for f in extract_dir.rglob("*_content_list.json")]
    if content_list_files:
        try:
            data = json.loads(content_list_files[0].read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return _parse_content_list(data, full_markdown)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # 3. Try layout.json with pdf_info
    layout_path = extract_dir / "layout.json"
    if layout_path.exists():
        try:
            data = json.loads(layout_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "pdf_info" in data:
                return _parse_pdf_info_json(data, full_markdown)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # 4. Fallback: use full.md as single page
    if full_markdown:
        return ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown=full_markdown)],
            parser_used="mineru",
        )

    raise MinerUAPIError(f"No parseable content in zip. Files: {list(extract_dir.rglob('*'))}")


def _parse_content_list(content_list: list[dict], full_markdown: str) -> ParseResult:
    """Parse MinerU *_content_list.json using production code path.

    Routes through MinerUParser._parse_content_list_json + _build_result
    to exercise the full production pipeline (including pages_from_raw,
    _figures_from_page, _tables_from_page).
    """
    parser = MinerUParser(api_token="dummy", poll_interval=0.1, max_poll_attempts=1)
    raw = parser._parse_content_list_json(content_list, full_markdown)
    return parser._build_result(raw)


def _parse_pdf_info_json(data: dict, full_markdown: str) -> ParseResult:
    """Parse MinerU layout.json pdf_info format.

    pdf_info entries have: preproc_blocks, page_idx, page_size, etc.
    page_content may be empty; use full.md as fallback.
    """
    pdf_info = data.get("pdf_info", [])
    if not pdf_info:
        return ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown=full_markdown)],
            parser_used="mineru",
        )

    pages = []
    for page_info in pdf_info:
        page_idx = page_info.get("page_idx", 0)
        page_number = page_idx + 1
        page_md = page_info.get("page_content", "") or page_info.get("markdown", "")
        pages.append(PageContent(page_number=page_number, markdown=page_md))

    # If all pages are empty, fall back to full_markdown split by page count
    if all(not p.markdown for p in pages):
        n = len(pages)
        if full_markdown:
            # Split roughly evenly
            chunk_size = len(full_markdown) // n
            for i in range(n):
                start = i * chunk_size
                end = start + chunk_size if i < n - 1 else len(full_markdown)
                pages[i] = PageContent(page_number=i + 1, markdown=full_markdown[start:end])

    return ParseResult(
        metadata=DocumentMetadata(total_pages=len(pages)),
        pages=pages,
        parser_used="mineru",
    )


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pdf_inventory():
    if not DOWNLOADS_DIR.exists():
        pytest.skip(f"PDF directory not found: {DOWNLOADS_DIR}")
    pdfs = _collect_pdfs()
    if not pdfs:
        pytest.skip("No PDFs found in downloads/")
    return pdfs


@pytest.fixture(scope="session")
def mineru_token():
    from src.core.config import get_config

    cfg = get_config()
    token = cfg.mineru_api_token
    if not token:
        pytest.skip("MINERU_API_TOKEN not configured")
    return token


@pytest.fixture
def local_parser():
    from src.core.config import get_config

    cfg = get_config()
    parser = MinerULocalParser(model_server_url=cfg.model_server_url)

    # Quick connectivity check
    import httpx

    try:
        resp = httpx.get(f"{cfg.model_server_url}/health", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        pytest.skip(f"model-server not available at {cfg.model_server_url}")

    return parser


# ── E2E Tests ───────────────────────────────────────────────────────────


@pytest.mark.integration
class TestMinerULocalE2E:
    """E2E tests for MinerU local mode (model-server VLM)."""

    @pytest.mark.asyncio
    async def test_single_pdf(self, pdf_inventory, local_parser):
        """Smoke test: parse first PDF to verify setup works."""
        pdf_path, lang = pdf_inventory[0]
        logger.info(f"E2E local: parsing {Path(pdf_path).name} ({lang})")

        result = await local_parser.parse(pdf_path)
        _assert_parse_result(result, pdf_path)

        out_dir = _save_output(lang, pdf_path, "local", result)
        assert (out_dir / "output.md").exists()
        assert (out_dir / "metadata.json").exists()
        assert (out_dir / "pages").is_dir()

        logger.info(
            f"E2E local: {Path(pdf_path).name} -> "
            f"{result.metadata.total_pages} pages, "
            f"{len(result.full_markdown)} chars markdown"
        )

    @pytest.mark.asyncio
    async def test_all_pdfs(self, pdf_inventory, local_parser):
        """Parse all PDFs with local MinerU VLM and save output."""
        results = []

        for pdf_path, lang in pdf_inventory:
            pdf_name = Path(pdf_path).name
            logger.info(f"E2E local: parsing {pdf_name} ({lang})")

            result = await local_parser.parse(pdf_path)
            _assert_parse_result(result, pdf_path)

            out_dir = _save_output(lang, pdf_path, "local", result)
            assert (out_dir / "output.md").exists()

            results.append((pdf_name, lang, result))
            logger.info(
                f"E2E local: {pdf_name} -> "
                f"{result.metadata.total_pages} pages, "
                f"{len(result.full_markdown)} chars"
            )

        # Summary
        logger.info(f"E2E local: completed {len(results)} PDFs")
        for pdf_name, lang, r in results:
            logger.info(f"  [{lang}] {pdf_name}: {r.metadata.total_pages} pages")


@pytest.mark.integration
class TestMinerUApiE2E:
    """E2E tests for MinerU API mode (cloud upload + batch poll)."""

    @pytest.mark.asyncio
    async def test_single_pdf(self, pdf_inventory, mineru_token):
        """Smoke test: upload and parse first PDF via MinerU cloud API."""
        pdf_path, lang = pdf_inventory[0]
        pdf_name = Path(pdf_path).name
        logger.info(f"E2E API: uploading {pdf_name} ({lang})")

        result = await _upload_and_parse_api(pdf_path, mineru_token)
        _assert_parse_result(result, pdf_path)

        out_dir = _save_output(lang, pdf_path, "api", result)
        assert (out_dir / "output.md").exists()
        assert (out_dir / "metadata.json").exists()

        logger.info(
            f"E2E API: {pdf_name} -> "
            f"{result.metadata.total_pages} pages, "
            f"{len(result.full_markdown)} chars markdown"
        )

    @pytest.mark.asyncio
    async def test_all_pdfs(self, pdf_inventory, mineru_token):
        """Upload and parse all PDFs via MinerU cloud API."""
        results = []

        for pdf_path, lang in pdf_inventory:
            pdf_name = Path(pdf_path).name
            logger.info(f"E2E API: uploading {pdf_name} ({lang})")

            result = await _upload_and_parse_api(pdf_path, mineru_token)
            _assert_parse_result(result, pdf_path)

            out_dir = _save_output(lang, pdf_path, "api", result)
            assert (out_dir / "output.md").exists()

            results.append((pdf_name, lang, result))
            logger.info(
                f"E2E API: {pdf_name} -> "
                f"{result.metadata.total_pages} pages, "
                f"{len(result.full_markdown)} chars"
            )

        # Summary
        logger.info(f"E2E API: completed {len(results)} PDFs")
        for pdf_name, lang, r in results:
            logger.info(f"  [{lang}] {pdf_name}: {r.metadata.total_pages} pages")


@pytest.mark.integration
class TestMinerUApiVsLocalComparison:
    """Compare API vs Local parser output for consistency."""

    @pytest.mark.asyncio
    async def test_page_count_matches(self, pdf_inventory, local_parser, mineru_token):
        """Verify API and local parsers agree on page count for each PDF."""
        for pdf_path, lang in pdf_inventory:
            pdf_name = Path(pdf_path).name
            logger.info(f"Comparing {pdf_name} ({lang})")

            local_result = await local_parser.parse(pdf_path)
            api_result = await _upload_and_parse_api(pdf_path, mineru_token)

            assert local_result.metadata.total_pages == api_result.metadata.total_pages, (
                f"Page count mismatch for {pdf_name}: "
                f"local={local_result.metadata.total_pages}, "
                f"api={api_result.metadata.total_pages}"
            )

            logger.info(
                f"  {pdf_name}: {local_result.metadata.total_pages} pages, "
                f"local={len(local_result.full_markdown)} chars, "
                f"api={len(api_result.full_markdown)} chars"
            )
