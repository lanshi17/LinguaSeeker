"""PDF to markdown parser using MinerU cloud API (primary) with pymupdf fallback.

MinerU API (https://mineru.net/api/v4):
  1. POST /file-urls/batch  — get presigned upload URLs + batch_id
  2. PUT {presigned_url}    — upload each local PDF
  3. GET /extract-results/batch/{batch_id} — poll until terminal
  4. Download zip from full_zip_url → extract full.md
"""
from __future__ import annotations

import asyncio
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger


class MinerUError(Exception):
    """MinerU API error."""


@dataclass
class MinerUConfig:
    base_url: str
    token: str
    model_version: str = "vlm"
    enable_formula: bool = True
    enable_table: bool = True
    language: str = "ch"
    poll_interval: float = 3.0
    max_poll_attempts: int = 200
    batch_size: int = 10


async def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _request_upload_urls(
    client: httpx.AsyncClient,
    config: MinerUConfig,
    file_names: list[str],
) -> tuple[str, list[str]]:
    """POST /file-urls/batch → (batch_id, presigned_urls)."""
    url = f"{config.base_url}/file-urls/batch"
    files = [{"name": name} for name in file_names]
    body: dict = {
        "files": files,
        "model_version": config.model_version,
        "enable_formula": config.enable_formula,
        "enable_table": config.enable_table,
        "language": config.language,
    }
    headers = await _auth_headers(config.token)

    resp = await client.post(url, json=body, headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()

    code = data.get("code")
    if code not in (0, "0"):
        raise MinerUError(f"Upload URL request failed: {data.get('msg', 'unknown')}")

    payload = data.get("data", {})
    batch_id = payload.get("batch_id", "")
    file_urls = payload.get("file_urls", [])

    if not batch_id or not file_urls:
        raise MinerUError(f"Invalid upload response: {payload}")

    return batch_id, file_urls


async def _upload_file(
    client: httpx.AsyncClient,
    presigned_url: str,
    file_path: Path,
) -> None:
    """PUT file bytes to presigned URL."""
    data = file_path.read_bytes()
    resp = await client.put(presigned_url, content=data, timeout=300.0)
    resp.raise_for_status()


async def _poll_batch(
    client: httpx.AsyncClient,
    config: MinerUConfig,
    batch_id: str,
) -> list[dict]:
    """Poll GET /extract-results/batch/{batch_id} until terminal."""
    url = f"{config.base_url}/extract-results/batch/{batch_id}"
    headers = await _auth_headers(config.token)

    for attempt in range(config.max_poll_attempts):
        resp = await client.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        code = data.get("code")
        if code not in (0, "0"):
            raise MinerUError(f"Batch poll failed: {data.get('msg', 'unknown')}")

        payload = data.get("data", {})
        extract_result = payload.get("extract_result", [])

        states = [item.get("state", "") for item in extract_result]
        if all(s in ("done", "failed") for s in states):
            return extract_result

        done = sum(1 for s in states if s == "done")
        total = len(states)
        if attempt % 10 == 0:
            logger.info("MinerU batch {}: {}/{} done (poll #{})", batch_id[:8], done, total, attempt)

        await asyncio.sleep(config.poll_interval)

    raise MinerUError(f"Batch {batch_id[:8]} timed out after {config.max_poll_attempts} polls")


async def _download_markdown(
    client: httpx.AsyncClient,
    zip_url: str,
) -> str:
    """Download result zip and extract full.md content."""
    resp = await client.get(zip_url, timeout=120.0)
    resp.raise_for_status()

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "result.zip"
        zip_path.write_bytes(resp.content)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        md_files = list(Path(tmp_dir).rglob("*.md"))
        full_md = Path(tmp_dir) / "full.md"
        if full_md.exists():
            return full_md.read_text(encoding="utf-8")

        if md_files:
            parts = [f.read_text(encoding="utf-8") for f in sorted(md_files)]
            return "\n\n".join(parts)

    raise MinerUError(f"No markdown found in zip from {zip_url}")


async def parse_pdfs_mineru(
    pdf_paths: list[Path],
    config: MinerUConfig,
) -> dict[str, str]:
    """Parse a batch of PDFs via MinerU cloud API.

    Returns: dict mapping pdf_path.name → markdown text.
    """
    results: dict[str, str] = {}

    for batch_start in range(0, len(pdf_paths), config.batch_size):
        batch = pdf_paths[batch_start: batch_start + config.batch_size]
        batch_num = batch_start // config.batch_size + 1
        total_batches = (len(pdf_paths) + config.batch_size - 1) // config.batch_size
        logger.info("MinerU batch {}/{}: {} files", batch_num, total_batches, len(batch))

        file_names = [p.name for p in batch]

        async with httpx.AsyncClient() as client:
            batch_id, presigned_urls = await _request_upload_urls(client, config, file_names)

            for url, path in zip(presigned_urls, batch):
                logger.debug("Uploading {}", path.name)
                await _upload_file(client, url, path)

            logger.info("Batch {} uploaded, polling...", batch_id[:8])
            extract_results = await _poll_batch(client, config, batch_id)

            for item in extract_results:
                file_name = item.get("file_name", "")
                state = item.get("state", "")
                if state != "done":
                    err = item.get("err_msg", "unknown")
                    logger.warning("MinerU failed for {}: {}", file_name, err)
                    continue

                zip_url = item.get("full_zip_url", "")
                if not zip_url:
                    logger.warning("No zip URL for done item: {}", file_name)
                    continue

                try:
                    md = await _download_markdown(client, zip_url)
                    md = _clean_markdown(md)
                    results[file_name] = md
                    logger.info("Parsed {}: {} chars", file_name, len(md))
                except Exception as e:
                    logger.error("Failed to extract {}: {}", file_name, e)

    return results


def _clean_markdown(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text.strip()


def detect_language_from_filename(filename: str) -> str:
    match = re.match(r"^([a-z]{2})_", filename)
    if match:
        return match.group(1)
    return "unknown"


def parse_pdf_pymupdf(pdf_path: Path) -> str:
    """Fallback: extract text from PDF using pymupdf."""
    import fitz

    doc = fitz.open(str(pdf_path))
    sections: list[str] = []
    for page in doc:
        text = page.get_text("text").strip()
        if text:
            sections.append(_clean_markdown(text))
    doc.close()
    return "\n\n".join(sections) if sections else ""
