"""Fetch PDFs for Parkinson literature publication records."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

import httpx

from lit_acquisition import (
    OnlineAcquisitionPubMedCandidate,
    OnlineAcquisitionPubMedService,
    get_pubmed_service,
)

DEFAULT_PUBLICATION_JSONL = Path("benchmark/data/processed/parkinson_literature/table7_publication_info.jsonl")
DEFAULT_OUTPUT_DIR = Path("benchmark/data/processed/parkinson_literature/publications")
PDF_MAGIC = b"%PDF"


class PubMedLookupService(Protocol):
    """Subset of PubMed service used by this dataset fetcher."""

    async def search_candidates(
        self,
        query: str,
        candidate_limit: int = 15,
    ) -> list[OnlineAcquisitionPubMedCandidate]:
        """Return PubMed candidates for a query."""


@dataclass(frozen=True)
class PublicationPdfRecord:
    """Download status for one publication row."""

    pmid: str
    row_number: int
    title: str
    pmcid: str = ""
    doi: str = ""
    pdf_url: str = ""
    pdf_path: str = ""
    status: str = "pending"
    warning: str = ""

    def to_json_dict(self) -> Mapping[str, object]:
        """Return a stable JSON object for this record."""
        return {
            "pmid": self.pmid,
            "row_number": self.row_number,
            "title": self.title,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "pdf_url": self.pdf_url,
            "pdf_path": self.pdf_path,
            "status": self.status,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class PublicationPdfFetchReport:
    """Summary of a publication PDF fetch run."""

    requested_count: int
    metadata_found_count: int
    downloadable_count: int
    downloaded_count: int
    records: tuple[PublicationPdfRecord, ...]

    def to_json_dict(self) -> Mapping[str, object]:
        """Return a stable JSON object for this fetch report."""
        return {
            "requested_count": self.requested_count,
            "metadata_found_count": self.metadata_found_count,
            "downloadable_count": self.downloadable_count,
            "downloaded_count": self.downloaded_count,
            "records": [record.to_json_dict() for record in self.records],
        }


async def fetch_publication_pdfs(
    *,
    publication_jsonl: Path = DEFAULT_PUBLICATION_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    pubmed_service: PubMedLookupService | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    start: int = 0,
    limit: int | None = None,
    concurrency: int = 1,
    force: bool = False,
) -> PublicationPdfFetchReport:
    """Fetch available PMC PDFs for publication rows in the normalized dataset."""
    service = pubmed_service or get_pubmed_service()
    publications = _load_publication_rows(publication_jsonl)
    if start > 0:
        publications = publications[start:]
    if limit is not None:
        publications = publications[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = output_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    records: list[PublicationPdfRecord] = []
    sem = asyncio.Semaphore(max(1, concurrency))
    async with httpx.AsyncClient(transport=transport, follow_redirects=True, timeout=60.0) as client:
        async def fetch_with_limit(row: Mapping[str, Any]) -> PublicationPdfRecord:
            async with sem:
                record = await _fetch_one(row, pdf_dir=pdf_dir, service=service, client=client, force=force)
                await asyncio.sleep(0.34)
                return record

        records = list(await asyncio.gather(*(fetch_with_limit(row) for row in publications)))

    report = PublicationPdfFetchReport(
        requested_count=len(publications),
        metadata_found_count=sum(1 for record in records if record.pmcid or record.doi),
        downloadable_count=sum(1 for record in records if record.pdf_url),
        downloaded_count=sum(1 for record in records if record.status == "downloaded"),
        records=tuple(records),
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


async def _fetch_one(
    row: Mapping[str, Any],
    *,
    pdf_dir: Path,
    service: PubMedLookupService,
    client: httpx.AsyncClient,
    force: bool,
) -> PublicationPdfRecord:
    pmid = str(row.get("Pubmed_id") or "").strip()
    title = str(row.get("Title") or "").strip()
    row_number = int(row.get("_row_number") or 0)
    if not pmid:
        return PublicationPdfRecord(pmid="", row_number=row_number, title=title, status="skipped", warning="missing_pmid")

    try:
        candidates = await service.search_candidates(f"{pmid}[PMID]", candidate_limit=1)
    except Exception as exc:
        return PublicationPdfRecord(
            pmid=pmid,
            row_number=row_number,
            title=title,
            status="metadata_error",
            warning=f"{type(exc).__name__}: {exc}",
        )
    if not candidates:
        return PublicationPdfRecord(pmid=pmid, row_number=row_number, title=title, status="metadata_missing")

    candidate = candidates[0]
    pdf_urls = _pmcid_pdf_urls(candidate.pmcid)
    if not pdf_urls:
        return PublicationPdfRecord(
            pmid=pmid,
            row_number=row_number,
            title=title or candidate.title,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            status="not_open_access",
            warning="missing_pmcid_pdf_url",
        )

    pdf_path = pdf_dir / f"{pmid}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 0 and not force:
        return PublicationPdfRecord(
            pmid=pmid,
            row_number=row_number,
            title=title or candidate.title,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            pdf_url=pdf_urls[0],
            pdf_path=str(pdf_path),
            status="exists",
        )

    warnings = []
    for pdf_url in pdf_urls:
        try:
            response = await client.get(pdf_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            warnings.append(f"{pdf_url}: {type(exc).__name__}")
            continue
        content = response.content
        if not content.startswith(PDF_MAGIC):
            warnings.append(f"{pdf_url}: response_not_pdf")
            continue
        pdf_path.write_bytes(content)
        return PublicationPdfRecord(
            pmid=pmid,
            row_number=row_number,
            title=title or candidate.title,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            pdf_url=pdf_url,
            pdf_path=str(pdf_path),
            status="downloaded",
        )
    return PublicationPdfRecord(
        pmid=pmid,
        row_number=row_number,
        title=title or candidate.title,
        pmcid=candidate.pmcid,
        doi=candidate.doi,
        pdf_url=pdf_urls[0],
        status="download_failed",
        warning="; ".join(warnings) or "download_failed",
    )


def _load_publication_rows(path: Path) -> list[Mapping[str, Any]]:
    rows = []
    seen_pmids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        pmid = str(payload.get("Pubmed_id") or "").strip()
        if not pmid or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)
        rows.append(payload)
    return rows


def _pmcid_pdf_urls(pmcid: str) -> tuple[str, ...]:
    normalized = pmcid.strip()
    if not normalized:
        return ()
    return (
        f"https://europepmc.org/articles/{normalized}?pdf=render",
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{normalized}/pdf/",
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for fetching Parkinson publication PDFs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-jsonl", type=Path, default=DEFAULT_PUBLICATION_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = asyncio.run(
        fetch_publication_pdfs(
            publication_jsonl=args.publication_jsonl,
            output_dir=args.output_dir,
            start=args.start,
            limit=args.limit,
            concurrency=args.concurrency,
            force=args.force,
            pubmed_service=OnlineAcquisitionPubMedService(),
        )
    )
    payload = report.to_json_dict()
    if args.quiet:
        print(
            json.dumps(
                {
                    "requested_count": payload["requested_count"],
                    "metadata_found_count": payload["metadata_found_count"],
                    "downloadable_count": payload["downloadable_count"],
                    "downloaded_count": payload["downloaded_count"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
