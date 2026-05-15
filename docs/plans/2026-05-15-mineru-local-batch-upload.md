# MinerU Local Batch Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a typed backend parse-document API that uploads local files through MinerU v4 batch upload, polls batch results, and converts completed result zips into existing `ParseResult` objects.

**Architecture:** Keep Rust `net-io` as the HTTP/upload provider because it already exposes `mineru_upload_local_files()` and `mineru_batch_result()`. Add Python feature-slice contracts in `parse_document/contracts.py`, orchestration methods in `MinerUParser` / `MinerURemoteParser`, and public facade methods in `ParseDocumentService`; reuse existing zip extraction and Markdown/image parsing instead of adding a second parsing path.

**Tech Stack:** Python 3.12, `uv`, pytest, Ruff, Pydantic, dataclasses, loguru, PyO3 Rust facade (`rust_io.net`), MinerU API v4.

**Status:** planned
**Created:** 2026-05-15
**Completed:** —
**PR:** —

---

## Context

The official MinerU v4 API supports local file batch upload through `POST /api/v4/file-urls/batch`, `PUT` to returned upload URLs, then polling `GET /api/v4/extract-results/batch/{batch_id}`. The current Rust layer already exposes these primitives:

- `backend/libs/net-io/src/mineru.rs`: `create_batch_upload_urls()`, `upload_local_files()`, `batch_result()`
- `backend/libs/net-io/src/py.rs`: `mineru_upload_local_files()`, `mineru_create_batch_upload_urls()`, `mineru_batch_result()`
- `backend/libs/rust-io/src/lib.rs`: registers those functions under `rust_io.net`

The current Python parse-document feature only exposes single URL parsing through `MinerUParser.parse(pdf_path)`, which calls `mineru_create_task()` and `mineru_get_result()`. This plan adds a Python-facing local-file batch parse workflow while preserving the existing single-file URL parser.

## Scope

In scope:

- Typed Python contracts for local batch upload requests, batch results, and parse outputs.
- `MinerUParser.upload_local_files()`, `MinerUParser.poll_batch_result()`, and `MinerUParser.parse_local_files()`.
- Public `ParseDocumentService.parse_local_files()` and `parse_local_files_and_save()`.
- Unit tests using patched `rust_io.net` functions; no live MinerU token required.
- README updates documenting local batch upload usage.

Out of scope:

- Callback endpoint implementation.
- Database persistence of batch task state.
- UI controls.
- Live MinerU integration tests as default CI tests.
- Rewriting the Rust upload implementation unless tests reveal a concrete defect.

## Success Criteria

- Local paths can be submitted as a batch with `model_version="vlm"` or `"pipeline"` and optional `data_ids`, `is_ocr`, `page_ranges`, `extra_formats`.
- Empty batches, more than 50 files, mismatched `data_ids`, missing local files, callback without seed, and unsupported extra formats fail before hitting MinerU.
- Batch polling accepts `waiting-file`, `pending`, `running`, and `converting` as in-progress states; returns when all files are terminal.
- Completed files with `full_zip_url` are downloaded and parsed through the existing zip parser, preserving Markdown and images.
- Failed batch entries are returned in a typed result instead of silently disappearing.
- Existing single URL parsing behavior is unchanged.
- `uv run pytest tests/core/ingest_and_digitize_data/parse_document/ -v --ignore=tests/core/ingest_and_digitize_data/parse_document/test_integration.py` passes.
- `uv run ruff check src/core/ingest_and_digitize_data/parse_document/ tests/core/ingest_and_digitize_data/parse_document/` passes.

---

### Task 1: Add Typed Batch Contracts

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`

**Step 1: Write the failing tests**

Append these tests to `backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py`:

```python
import pytest
from pydantic import ValidationError

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    MinerUBatchExtractProgress,
    MinerUBatchFileResult,
    MinerULocalBatchOptions,
    MinerULocalBatchUploadResult,
)


def test_local_batch_options_rejects_callback_without_seed() -> None:
    with pytest.raises(ValidationError, match="seed is required"):
        MinerULocalBatchOptions(callback="https://example.com/callback")


def test_local_batch_options_rejects_unsupported_extra_format() -> None:
    with pytest.raises(ValidationError, match="extra_formats"):
        MinerULocalBatchOptions(extra_formats=["xlsx"])


def test_batch_upload_result_requires_matching_url_count() -> None:
    with pytest.raises(ValueError, match="upload URL count"):
        MinerULocalBatchUploadResult(batch_id="batch-1", file_paths=["a.pdf", "b.pdf"], file_urls=["https://u1"])


def test_batch_file_result_done_property() -> None:
    item = MinerUBatchFileResult(file_name="demo.pdf", state="done", full_zip_url="https://example.com/result.zip")
    assert item.is_done is True
    assert item.is_terminal is True


def test_batch_file_result_running_progress() -> None:
    item = MinerUBatchFileResult(
        file_name="demo.pdf",
        state="running",
        extract_progress=MinerUBatchExtractProgress(extracted_pages=1, total_pages=2, start_time="2026-05-15 10:00:00"),
    )
    assert item.is_done is False
    assert item.is_terminal is False
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py -v
```

Expected: FAIL with import errors for the new contract names.

**Step 3: Add the minimal contracts**

Add these imports near the top of `contracts.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field, model_validator
```

`Literal` and `BaseModel` already exist in the file, so do not duplicate imports; only adjust what is missing.

Add these models after `DedupResult`:

```python
MinerUModelVersion = Literal["pipeline", "vlm", "MinerU-HTML"]
MinerUExtraFormat = Literal["docx", "html", "latex"]
MinerUBatchState = Literal["waiting-file", "pending", "running", "converting", "done", "failed"]


class MinerULocalBatchOptions(BaseModel):
    """Options shared by MinerU local-file batch upload."""

    model_version: MinerUModelVersion = "vlm"
    enable_formula: bool | None = True
    enable_table: bool | None = True
    language: str | None = "ch"
    data_ids: list[str] | None = None
    is_ocr: bool | None = None
    page_ranges: str | None = None
    callback: str | None = None
    seed: str | None = None
    extra_formats: list[MinerUExtraFormat] | None = None
    timeout_ms: int | None = None
    proxy: str | None = None

    @model_validator(mode="after")
    def _validate_callback_seed(self) -> "MinerULocalBatchOptions":
        if self.callback and not self.seed:
            raise ValueError("seed is required when callback is set")
        return self


class MinerULocalBatchUploadResult(BaseModel):
    """Result returned after MinerU upload URLs are created and files are PUT."""

    batch_id: str
    file_paths: list[str]
    file_urls: list[str]
    trace_id: str | None = None
    message: str = "ok"

    @model_validator(mode="after")
    def _validate_file_url_count(self) -> "MinerULocalBatchUploadResult":
        if len(self.file_urls) != len(self.file_paths):
            raise ValueError("upload URL count must match file path count")
        return self


class MinerUBatchExtractProgress(BaseModel):
    """MinerU per-file extraction progress."""

    extracted_pages: int = 0
    total_pages: int = 0
    start_time: str | None = None


class MinerUBatchFileResult(BaseModel):
    """MinerU result for one file in a batch."""

    file_name: str
    state: MinerUBatchState
    err_msg: str = ""
    data_id: str | None = None
    full_zip_url: str | None = None
    extract_progress: MinerUBatchExtractProgress | None = None

    @property
    def is_done(self) -> bool:
        return self.state == "done"

    @property
    def is_terminal(self) -> bool:
        return self.state in {"done", "failed"}


class MinerUBatchStatus(BaseModel):
    """Typed MinerU batch polling response data."""

    batch_id: str
    extract_result: list[MinerUBatchFileResult] = Field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return bool(self.extract_result) and all(item.is_terminal for item in self.extract_result)
```

Update `__all__` later in Task 5; this file currently has no local `__all__`.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_contracts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_contracts.py
git commit -m "feat: add mineru batch parse contracts"
```

---

### Task 2: Validate Local Batch Inputs Before Network Calls

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the failing tests**

Append these tests to `TestMinerUParser` in `test_mineru_parser.py`:

```python
    def test_validate_local_batch_rejects_empty_file_list(self, parser):
        with pytest.raises(MinerUAPIError, match="at least one file"):
            parser._validate_local_batch_inputs([], None)

    def test_validate_local_batch_rejects_more_than_50_files(self, parser, tmp_path):
        paths = []
        for index in range(51):
            file_path = tmp_path / f"paper-{index}.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")
            paths.append(str(file_path))

        with pytest.raises(MinerUAPIError, match="50 files"):
            parser._validate_local_batch_inputs(paths, None)

    def test_validate_local_batch_rejects_missing_file(self, parser, tmp_path):
        missing = tmp_path / "missing.pdf"

        with pytest.raises(MinerUAPIError, match="does not exist"):
            parser._validate_local_batch_inputs([str(missing)], None)

    def test_validate_local_batch_rejects_data_id_length_mismatch(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")

        with pytest.raises(MinerUAPIError, match="data_ids length"):
            parser._validate_local_batch_inputs([str(file_path)], ["id-1", "id-2"])
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser -v
```

Expected: FAIL with `AttributeError: 'MinerUParser' object has no attribute '_validate_local_batch_inputs'`.

**Step 3: Implement validation helper**

Add this method to `MinerUParser` before `_create_task()`:

```python
    def _validate_local_batch_inputs(self, file_paths: list[str], data_ids: list[str] | None) -> None:
        """Validate MinerU local-file batch constraints before API calls."""
        if not file_paths:
            raise MinerUAPIError("MinerU local batch requires at least one file")
        if len(file_paths) > 50:
            raise MinerUAPIError("MinerU local batch cannot exceed 50 files")
        if data_ids is not None and len(data_ids) != len(file_paths):
            raise MinerUAPIError("data_ids length must match file_paths length")

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                raise MinerUAPIError(f"Local file does not exist: {file_path}")
            if not path.is_file():
                raise MinerUAPIError(f"Local path is not a file: {file_path}")
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser -v
```

Expected: PASS for the new validation tests and no regressions in existing parser tests.

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat: validate mineru local batch inputs"
```

---

### Task 3: Add Batch Upload and Batch Polling Methods

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the failing tests**

Append these tests to `TestMinerUParser`:

```python
    @pytest.mark.asyncio
    async def test_upload_local_files_returns_typed_upload_result(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        upload_response = {
            "code": 0,
            "msg": "ok",
            "trace_id": "trace-1",
            "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example/paper"]},
        }

        with patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response) as upload:
            result = await parser.upload_local_files([str(file_path)], data_ids=["paper-1"], model_version="vlm")

        assert result.batch_id == "batch-1"
        assert result.file_paths == [str(file_path)]
        assert result.file_urls == ["https://upload.example/paper"]
        upload.assert_awaited_once_with(
            file_paths=[str(file_path)],
            token="test-token",
            model_version="vlm",
            enable_formula=True,
            enable_table=True,
            language="ch",
            data_ids=["paper-1"],
            is_ocr=None,
            page_ranges=None,
            callback=None,
            seed=None,
            extra_formats=None,
            timeout_ms=None,
            proxy=None,
        )

    @pytest.mark.asyncio
    async def test_upload_local_files_rejects_api_error_code(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        upload_response = {"code": -60005, "msg": "file too large", "data": {}}

        with patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response):
            with pytest.raises(MinerUAPIError, match="file too large"):
                await parser.upload_local_files([str(file_path)])

    @pytest.mark.asyncio
    async def test_poll_batch_result_returns_terminal_status(self, parser):
        response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [
                    {"file_name": "paper.pdf", "state": "done", "full_zip_url": "https://example.com/result.zip", "err_msg": ""}
                ],
            },
        }

        with patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=response) as poll:
            result = await parser.poll_batch_result("batch-1")

        assert result.batch_id == "batch-1"
        assert result.is_terminal is True
        assert result.extract_result[0].full_zip_url == "https://example.com/result.zip"
        poll.assert_awaited_once_with(batch_id="batch-1", token="test-token", timeout_ms=None, proxy=None)

    @pytest.mark.asyncio
    async def test_poll_batch_until_terminal_times_out(self, parser):
        response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [{"file_name": "paper.pdf", "state": "running", "err_msg": ""}],
            },
        }

        with patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=response):
            with pytest.raises(MinerUTimeoutError):
                await parser.poll_batch_until_terminal("batch-1")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser -v
```

Expected: FAIL with missing `upload_local_files`, `poll_batch_result`, and `poll_batch_until_terminal`.

**Step 3: Import contracts**

Update the contract import in `mineru_parser.py`:

```python
from .contracts import (
    DocumentMetadata,
    MinerUBatchStatus,
    MinerULocalBatchOptions,
    MinerULocalBatchUploadResult,
    ParseResult,
    pages_from_raw,
)
```

**Step 4: Implement API response guard**

Add this private helper to `MinerUParser`:

```python
    def _require_success_response(self, response: dict, operation: str) -> dict:
        """Return response data or raise a MinerUAPIError."""
        code = response.get("code")
        if code not in (0, "0"):
            message = response.get("msg", "unknown MinerU error")
            raise MinerUAPIError(f"{operation} failed: {message}")

        data = response.get("data", {})
        if not isinstance(data, dict):
            raise MinerUAPIError(f"{operation} returned invalid data: {response}")
        return data
```

**Step 5: Implement upload and polling methods**

Add these methods to `MinerUParser` after `_validate_local_batch_inputs()`:

```python
    async def upload_local_files(
        self,
        file_paths: list[str],
        *,
        model_version: str = "vlm",
        enable_formula: bool | None = True,
        enable_table: bool | None = True,
        language: str | None = "ch",
        data_ids: list[str] | None = None,
        is_ocr: bool | None = None,
        page_ranges: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: list[str] | None = None,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerULocalBatchUploadResult:
        """Upload local files through MinerU batch upload URLs."""
        options = MinerULocalBatchOptions(
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            data_ids=data_ids,
            is_ocr=is_ocr,
            page_ranges=page_ranges,
            callback=callback,
            seed=seed,
            extra_formats=extra_formats,
            timeout_ms=timeout_ms,
            proxy=proxy,
        )
        self._validate_local_batch_inputs(file_paths, options.data_ids)

        try:
            response = await net_io.mineru_upload_local_files(
                file_paths=file_paths,
                token=self._api_token,
                model_version=options.model_version,
                enable_formula=options.enable_formula,
                enable_table=options.enable_table,
                language=options.language,
                data_ids=options.data_ids,
                is_ocr=options.is_ocr,
                page_ranges=options.page_ranges,
                callback=options.callback,
                seed=options.seed,
                extra_formats=options.extra_formats,
                timeout_ms=options.timeout_ms,
                proxy=options.proxy,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to upload local files: {e}") from e

        data = self._require_success_response(response, "MinerU local batch upload")
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls")
        if not isinstance(batch_id, str) or not isinstance(file_urls, list):
            raise MinerUAPIError(f"Invalid upload response: {response}")

        return MinerULocalBatchUploadResult(
            batch_id=batch_id,
            file_paths=file_paths,
            file_urls=file_urls,
            trace_id=response.get("trace_id"),
            message=response.get("msg", "ok"),
        )

    async def poll_batch_result(
        self,
        batch_id: str,
        *,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerUBatchStatus:
        """Fetch the current MinerU batch status once."""
        try:
            response = await net_io.mineru_batch_result(
                batch_id=batch_id,
                token=self._api_token,
                timeout_ms=timeout_ms,
                proxy=proxy,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to get batch result: {e}") from e

        data = self._require_success_response(response, "MinerU batch result")
        return MinerUBatchStatus.model_validate(data)

    async def poll_batch_until_terminal(
        self,
        batch_id: str,
        *,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerUBatchStatus:
        """Poll MinerU batch status until every file is done or failed."""
        for _attempt in range(self._max_poll_attempts):
            status = await self.poll_batch_result(batch_id, timeout_ms=timeout_ms, proxy=proxy)
            if status.is_terminal:
                return status
            await asyncio.sleep(self._poll_interval)

        raise MinerUTimeoutError(total_timeout=self._poll_interval * self._max_poll_attempts)
```

**Step 6: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat: add mineru local batch upload polling"
```

---

### Task 4: Convert Completed Batch Zips to ParseResult Objects

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the failing test**

Append this test to `TestMinerUParser`:

```python
    @pytest.mark.asyncio
    async def test_parse_local_files_returns_results_and_failed_entries(self, parser, tmp_path):
        first = tmp_path / "first.pdf"
        second = tmp_path / "second.pdf"
        first.write_bytes(b"%PDF-1.4\n")
        second.write_bytes(b"%PDF-1.4\n")

        upload_response = {
            "code": 0,
            "msg": "ok",
            "data": {"batch_id": "batch-1", "file_urls": ["https://upload/1", "https://upload/2"]},
        }
        status_response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [
                    {"file_name": "first.pdf", "state": "done", "full_zip_url": "https://example.com/first.zip", "err_msg": ""},
                    {"file_name": "second.pdf", "state": "failed", "err_msg": "parse failed"},
                ],
            },
        }

        raw = {
            "state": "done",
            "total_pages": 1,
            "title": "First",
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "# First", "figures": [], "tables": []}],
            "full_markdown": "# First",
            "images": {},
        }

        with patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response), \
             patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=status_response), \
             patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock, return_value=raw):
            result = await parser.parse_local_files([str(first), str(second)])

        assert result.batch_id == "batch-1"
        assert list(result.results.keys()) == ["first.pdf"]
        assert result.results["first.pdf"].full_markdown == "# First"
        assert result.failed_files == ["second.pdf"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_parse_local_files_returns_results_and_failed_entries -v
```

Expected: FAIL with missing `parse_local_files` and `MinerULocalBatchParseResult`.

**Step 3: Add parse result contract**

Add this Pydantic model to `contracts.py` after `MinerUBatchStatus`:

```python
class MinerULocalBatchParseResult(BaseModel):
    """Parsed output for a MinerU local-file batch."""

    batch_id: str
    status: MinerUBatchStatus
    results: dict[str, ParseResult] = Field(default_factory=dict)

    @property
    def failed_files(self) -> list[str]:
        return [item.file_name for item in self.status.extract_result if item.state == "failed"]
```

This is not a backend function return annotation with bare `dict`; it is a named Pydantic API/domain contract. It satisfies the project rule for typed contracts.

**Step 4: Implement `parse_local_files()`**

Import the contract in `mineru_parser.py`:

```python
    MinerULocalBatchParseResult,
```

Add this method to `MinerUParser` after `poll_batch_until_terminal()`:

```python
    async def parse_local_files(
        self,
        file_paths: list[str],
        *,
        model_version: str = "vlm",
        enable_formula: bool | None = True,
        enable_table: bool | None = True,
        language: str | None = "ch",
        data_ids: list[str] | None = None,
        is_ocr: bool | None = None,
        page_ranges: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: list[str] | None = None,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerULocalBatchParseResult:
        """Upload local files, wait for MinerU completion, and parse completed zips."""
        upload = await self.upload_local_files(
            file_paths,
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            data_ids=data_ids,
            is_ocr=is_ocr,
            page_ranges=page_ranges,
            callback=callback,
            seed=seed,
            extra_formats=extra_formats,
            timeout_ms=timeout_ms,
            proxy=proxy,
        )
        status = await self.poll_batch_until_terminal(upload.batch_id, timeout_ms=timeout_ms, proxy=proxy)

        parsed: dict[str, ParseResult] = {}
        for item in status.extract_result:
            if item.state != "done":
                logger.warning(f"MinerU batch file failed or incomplete: {item.file_name}: {item.err_msg}")
                continue
            if not item.full_zip_url:
                raise MinerUAPIError(f"Done batch item has no full_zip_url: {item.file_name}")
            raw = await self._download_and_parse_zip(item.full_zip_url)
            parsed[item.file_name] = self._build_result(raw)

        return MinerULocalBatchParseResult(batch_id=upload.batch_id, status=status, results=parsed)
```

**Step 5: Run targeted test**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_parse_local_files_returns_results_and_failed_entries -v
```

Expected: PASS.

**Step 6: Run full parser tests**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
  backend/src/core/ingest_and_digitize_data/parse_document/mineru_parser.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "feat: parse mineru local batch results"
```

---

### Task 5: Expose Batch Parsing Through Remote Parser and Service

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py`

**Step 1: Write the failing service tests**

Append these tests to `TestParseDocumentService`:

```python
    @pytest.mark.asyncio
    async def test_parse_local_files_delegates_to_remote_batch_parser(self, service, mock_orchestrator, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        expected = MagicMock()
        mock_orchestrator.parse_local_files = AsyncMock(return_value=expected)

        result = await service.parse_local_files([str(file_path)], data_ids=["paper-1"])

        assert result is expected
        mock_orchestrator.parse_local_files.assert_awaited_once_with([str(file_path)], data_ids=["paper-1"])

    @pytest.mark.asyncio
    async def test_parse_local_files_requires_orchestrator_support(self, service, mock_orchestrator, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        if hasattr(mock_orchestrator, "parse_local_files"):
            del mock_orchestrator.parse_local_files

        with pytest.raises(AttributeError, match="parse_local_files"):
            await service.parse_local_files([str(file_path)])
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v
```

Expected: FAIL with missing service method.

**Step 3: Add service method**

Import the batch parse result in `service.py`:

```python
    MinerULocalBatchParseResult,
```

Add this method to `ParseDocumentService` after `parse()`:

```python
    async def parse_local_files(self, file_paths: list[str], **kwargs) -> MinerULocalBatchParseResult:
        """Parse local files through a MinerU remote batch upload workflow."""
        parser = getattr(self._orchestrator, "parse_local_files", None)
        if parser is None:
            raise AttributeError("Configured parser does not support parse_local_files")
        return await parser(file_paths, **kwargs)
```

This uses `**kwargs` only as a pass-through facade to the typed parser method; do not add business logic here.

**Step 4: Export contracts from `__init__.py`**

Add these names to the import from `.contracts` and to `__all__`:

```python
    MinerUBatchExtractProgress,
    MinerUBatchFileResult,
    MinerUBatchStatus,
    MinerULocalBatchOptions,
    MinerULocalBatchParseResult,
    MinerULocalBatchUploadResult,
```

**Step 5: Add import smoke test**

Append this to `backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py`:

```python
def test_batch_contracts_exported():
    from src.core.ingest_and_digitize_data.parse_document import (
        MinerUBatchStatus,
        MinerULocalBatchOptions,
        MinerULocalBatchParseResult,
    )

    assert MinerUBatchStatus is not None
    assert MinerULocalBatchOptions is not None
    assert MinerULocalBatchParseResult is not None
```

**Step 6: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py \
  tests/core/ingest_and_digitize_data/parse_document/test_init.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/service.py \
  backend/src/core/ingest_and_digitize_data/parse_document/__init__.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_init.py
git commit -m "feat: expose mineru local batch parsing service"
```

---

### Task 6: Add Save Helper for Batch Parse Results

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/contracts.py`
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/service.py`
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py`

**Step 1: Write the failing test**

Append this test to `TestParseDocumentService`:

```python
    @pytest.mark.asyncio
    async def test_parse_local_files_and_save_writes_each_completed_file(self, service, mock_orchestrator, tmp_path):
        from src.core.ingest_and_digitize_data.parse_document.contracts import (
            MinerUBatchFileResult,
            MinerUBatchStatus,
            MinerULocalBatchParseResult,
        )

        batch_result = MinerULocalBatchParseResult(
            batch_id="batch-1",
            status=MinerUBatchStatus(
                batch_id="batch-1",
                extract_result=[MinerUBatchFileResult(file_name="paper.pdf", state="done", full_zip_url="https://example.com/paper.zip")],
            ),
            results={
                "paper.pdf": ParseResult(
                    metadata=DocumentMetadata(total_pages=1, title="Paper"),
                    pages=[PageContent(page_number=1, markdown="# Paper")],
                    parser_used="mineru-remote",
                )
            },
        )
        mock_orchestrator.parse_local_files = AsyncMock(return_value=batch_result)

        result = await service.parse_local_files_and_save(["/tmp/paper.pdf"], str(tmp_path))

        assert result.batch_id == "batch-1"
        assert "paper.pdf" in result.saved_files
        assert result.saved_files["paper.pdf"].md_path.exists()
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py::TestParseDocumentService::test_parse_local_files_and_save_writes_each_completed_file -v
```

Expected: FAIL with missing `parse_local_files_and_save`.

**Step 3: Add saved batch contract**

Add this dataclass to `contracts.py` after `ParseAndSaveResult`:

```python
@dataclass
class MinerULocalBatchSaveResult:
    """Saved output paths for a MinerU local-file batch."""

    batch_id: str
    parse_result: MinerULocalBatchParseResult
    saved_files: dict[str, SavedFiles]
```

This is a named dataclass contract; the internal mapping is acceptable as a field, not as a bare function return type.

**Step 4: Implement service helper**

Import `MinerULocalBatchSaveResult` in `service.py`, then add:

```python
    async def parse_local_files_and_save(
        self,
        file_paths: list[str],
        output_dir: str,
        **kwargs,
    ) -> MinerULocalBatchSaveResult:
        """Parse local files as a MinerU batch and save each completed result."""
        parse_result = await self.parse_local_files(file_paths, **kwargs)
        root = Path(output_dir)
        saved: dict[str, SavedFiles] = {}
        for file_name, result in parse_result.results.items():
            file_output_dir = root / Path(file_name).stem
            saved[file_name] = await self.save(result, str(file_output_dir))
        return MinerULocalBatchSaveResult(
            batch_id=parse_result.batch_id,
            parse_result=parse_result,
            saved_files=saved,
        )
```

**Step 5: Export contract**

Add `MinerULocalBatchSaveResult` to `backend/src/core/ingest_and_digitize_data/parse_document/__init__.py` imports and `__all__`.

**Step 6: Run service tests**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/contracts.py \
  backend/src/core/ingest_and_digitize_data/parse_document/service.py \
  backend/src/core/ingest_and_digitize_data/parse_document/__init__.py \
  backend/tests/core/ingest_and_digitize_data/parse_document/test_service.py
git commit -m "feat: save mineru local batch parse outputs"
```

---

### Task 7: Add Regression Test for Existing Single-URL Parser Behavior

**Files:**
- Test: `backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py`

**Step 1: Write the regression test**

Append this test to `TestMinerUParser`:

```python
    @pytest.mark.asyncio
    async def test_single_url_parse_still_uses_create_task_not_batch_upload(self, parser):
        mock_create_response = {"code": 0, "data": {"task_id": "task-1"}, "msg": "ok"}
        mock_poll_response = {"code": 0, "data": {"state": "done", "full_zip_url": "https://example.com/result.zip"}, "msg": "ok"}
        raw = {
            "state": "done",
            "total_pages": 1,
            "title": None,
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "ok", "figures": [], "tables": []}],
            "full_markdown": "ok",
            "images": {},
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response) as create_task, \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_poll_response), \
             patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock) as upload_local_files, \
             patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock, return_value=raw):
            result = await parser.parse("https://example.com/paper.pdf")

        assert result.full_markdown == "ok"
        create_task.assert_awaited_once()
        upload_local_files.assert_not_called()
```

**Step 2: Run test**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py::TestMinerUParser::test_single_url_parse_still_uses_create_task_not_batch_upload -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/parse_document/test_mineru_parser.py
git commit -m "test: preserve mineru single url parsing path"
```

---

### Task 8: Document Local Batch Upload API

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/README.md`
- Modify: `progress.txt`

**Step 1: Update README quick start**

Add this example after the existing single-file quick start:

````markdown
### Local File Batch Upload

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

service = create_parse_service()

result = await service.parse_local_files(
    ["downloads/en/paper.pdf", "downloads/zh/paper.pdf"],
    model_version="vlm",
    data_ids=["paper-en", "paper-zh"],
    is_ocr=True,
)

for file_name, parse_result in result.results.items():
    print(file_name, parse_result.full_markdown[:200])

print(result.failed_files)
```
````

**Step 2: Update public API table**

Add rows to the `ParseDocumentService` table:

```markdown
| `parse_local_files` | `async (file_paths: list[str], **kwargs) -> MinerULocalBatchParseResult` | Upload local files with MinerU batch API, poll results, parse completed zips |
| `parse_local_files_and_save` | `async (file_paths: list[str], output_dir: str, **kwargs) -> MinerULocalBatchSaveResult` | Batch parse local files and save each completed result under `output_dir/<file_stem>/` |
```

**Step 3: Add contract section**

Add a compact section after `ParseAndSaveResult`:

```markdown
### MinerU Local Batch Contracts

| Contract | Description |
|----------|-------------|
| `MinerULocalBatchOptions` | Shared upload options: model version, OCR, formula/table toggles, language, data IDs, callback/seed, extra formats, timeout/proxy |
| `MinerULocalBatchUploadResult` | Upload response with `batch_id`, local paths, pre-signed upload URLs, trace ID, and message |
| `MinerUBatchStatus` | Current batch status from `extract-results/batch/{batch_id}` |
| `MinerUBatchFileResult` | Per-file state, error message, data ID, `full_zip_url`, and progress |
| `MinerULocalBatchParseResult` | Completed batch parse output keyed by MinerU file name, with `failed_files` helper |
| `MinerULocalBatchSaveResult` | Saved output paths for each completed batch file |
```

**Step 4: Add progress entry**

Append this line to `progress.txt`:

```text
[2026-05-15] Planned MinerU local-file batch upload API for parse_document using existing rust_io.net MinerU upload primitives [planned]
```

**Step 5: Run docs smoke check**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_service.py \
  tests/core/ingest_and_digitize_data/parse_document/test_init.py -v
```

Expected: PASS. Documentation-only changes should not affect tests.

**Step 6: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/README.md progress.txt
git commit -m "docs: document mineru local batch parsing"
```

---

### Task 9: Verify Rust Facade Still Exposes Upload Primitives

**Files:**
- Test only unless a concrete failure is found:
  - `backend/libs/net-io/src/mineru.rs`
  - `backend/libs/net-io/src/py.rs`
  - `backend/libs/rust-io/src/lib.rs`

**Step 1: Run existing Rust tests**

Run:

```bash
cd backend/libs/net-io
cargo test mineru
```

Expected: PASS, including tests for `build_batch_upload_url_body()` and `extract_upload_urls()`.

**Step 2: Run Rust facade tests/build**

Run:

```bash
cd backend/libs/rust-io
cargo test
```

Expected: PASS. If the crate has no Rust tests, build/test should still finish successfully.

**Step 3: Only if a facade exposure gap is found, patch the facade**

Expected current state: `backend/libs/rust-io/src/lib.rs` already registers:

```rust
net.add_function(wrap_pyfunction!(net_io::py::mineru_batch_result, &net)?)?;
net.add_function(wrap_pyfunction!(net_io::py::mineru_create_batch_upload_urls, &net)?)?;
net.add_function(wrap_pyfunction!(net_io::py::mineru_upload_local_files, &net)?)?;
```

If any of these are missing in the implementation branch, add them back and rerun both Rust commands.

**Step 4: Commit only if code changed**

```bash
git add backend/libs/net-io/src/mineru.rs backend/libs/net-io/src/py.rs backend/libs/rust-io/src/lib.rs
git commit -m "fix: expose mineru local batch upload facade"
```

If no code changed, do not create an empty commit.

---

### Task 10: Final Verification

**Files:**
- No source changes expected.

**Step 1: Run backend parse-document unit tests**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/ \
  tests/core/test_parse_document_config.py \
  -v \
  --ignore=tests/core/ingest_and_digitize_data/parse_document/test_integration.py
```

Expected: PASS.

**Step 2: Run lint**

Run:

```bash
cd backend
uv run ruff check src/core/ingest_and_digitize_data/parse_document/ \
  tests/core/ingest_and_digitize_data/parse_document/ \
  tests/core/test_parse_document_config.py
```

Expected: PASS.

**Step 3: Run Rust tests**

Run:

```bash
cd backend/libs/net-io
cargo test mineru
```

Expected: PASS.

Run:

```bash
cd backend/libs/rust-io
cargo test
```

Expected: PASS.

**Step 4: Optional live smoke test**

Only run when `MINERU_REMOTE_API_TOKEN` is set and the user explicitly wants a live MinerU call:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_e2e_mineru.py -v -m integration
```

Expected: PASS against the live MinerU service. Do not run by default in CI because it consumes quota and requires credentials.

**Step 5: Append completion progress**

Append after all verification passes:

```text
[2026-05-15] Implemented MinerU local-file batch upload API for parse_document with typed contracts, polling, zip parsing, service facade, docs, and tests [done]
```

**Step 6: Final commit**

If Task 10 produced only `progress.txt` changes:

```bash
git add progress.txt
git commit -m "chore: record mineru local batch upload completion"
```

---

## Implementation Notes

- Prefer `MinerURemoteParser.parse_local_files()` over adding batch methods to `DocumentParseOrchestrator`. Local file upload is explicitly a MinerU remote API capability; the local VLM parser cannot consume arbitrary DOC/DOCX/PPT/PPTX formats and should not pretend to be a batch upload backend.
- Keep callback support as parameter pass-through only. Do not implement a FastAPI callback endpoint in this feature.
- Do not add raw `-> dict` function return annotations. Use the named Pydantic/dataclass contracts listed above.
- Do not add new dependencies. Existing `rust_io.net`, `httpx`, Pydantic, pytest, and loguru are enough.
- Preserve existing single-file URL parsing through `parse()` and `mineru_create_task()`.
- MinerU says upload `PUT` should omit `Content-Type`; the Rust implementation already passes `None` for local-file batch upload.
- The maximum batch size is 50 files. Enforce this in Python before calling Rust so errors are immediate and testable.

## Code Review Checklist

- [ ] No API token or credential appears in tests, docs, or logs.
- [ ] `callback` cannot be set without `seed`.
- [ ] `extra_formats` only accepts `docx`, `html`, and `latex`.
- [ ] Existing URL parser tests still pass.
- [ ] Failed MinerU files are represented in `MinerULocalBatchParseResult.status`, not thrown away.
- [ ] Completed files without `full_zip_url` raise `MinerUAPIError`.
- [ ] README includes the batch API and clearly says live MinerU tests are optional.
