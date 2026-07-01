"""Tests for Parkinson literature XLSX dataset curation."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from benchmark.datasets.parkinson_literature.fetch_pdfs import fetch_publication_pdfs
from benchmark.datasets.parkinson_literature.export_dataset import export_dataset
from benchmark.datasets.parkinson_literature.xlsx_dataset import (
    build_audit_report,
    load_workbook_tables,
    normalize_missing,
    normalize_pubmed_id,
)


def test_normalize_missing_handles_common_placeholders() -> None:
    assert normalize_missing("") is None
    assert normalize_missing(" / ") is None
    assert normalize_missing("\\") is None
    assert normalize_missing(" value ") == "value"


def test_normalize_pubmed_id_removes_excel_float_suffix() -> None:
    assert normalize_pubmed_id("16643317.0") == "16643317"
    assert normalize_pubmed_id(16643317) == "16643317"
    assert normalize_pubmed_id("/") is None


def test_load_workbook_tables_reads_headers_and_normalized_rows(tmp_path: Path) -> None:
    workbook_path = _write_minimal_xlsx(tmp_path / "sample.xlsx")

    tables = load_workbook_tables(workbook_path)

    assert tuple(tables) == ("table7_publication_info",)
    table = tables["table7_publication_info"]
    assert table.headers == ("Pubmed_id", "Title")
    assert table.rows[0]["Pubmed_id"] == "16643317"
    assert table.rows[0]["Title"] == "Parkin study"
    assert table.rows[1]["Pubmed_id"] is None
    assert table.rows[1]["Title"] is None
    assert table.row_numbers == (2, 3)


def test_build_audit_report_profiles_tables(tmp_path: Path) -> None:
    workbook_path = _write_minimal_xlsx(tmp_path / "sample.xlsx")
    tables = load_workbook_tables(workbook_path)

    report = build_audit_report(tables)
    payload = report.to_json_dict()

    assert payload["sheet_count"] == 1
    assert payload["total_data_rows"] == 2
    sheet = payload["sheets"][0]
    assert sheet["name"] == "table7_publication_info"
    assert sheet["data_rows"] == 2
    assert sheet["column_count"] == 2
    assert sheet["non_empty_counts"]["Pubmed_id"] == 1
    assert sheet["identifier_counts"]["Pubmed_id"] == 1
    json.dumps(payload)


def test_export_dataset_writes_audit_and_jsonl(tmp_path: Path) -> None:
    workbook_path = _write_minimal_xlsx(tmp_path / "sample.xlsx")
    output_dir = tmp_path / "out"

    paths = export_dataset(input_path=workbook_path, output_dir=output_dir)

    audit = json.loads(paths.audit_report.read_text(encoding="utf-8"))
    assert audit["sheet_count"] == 1
    jsonl_path = output_dir / "table7_publication_info.jsonl"
    assert paths.jsonl_paths == (jsonl_path,)
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["_sheet"] == "table7_publication_info"
    assert rows[0]["_row_number"] == 2
    assert rows[0]["Pubmed_id"] == "16643317"


@pytest.mark.asyncio
async def test_fetch_publication_pdfs_uses_pubmed_service_and_writes_pdf(tmp_path: Path) -> None:
    publication_jsonl = tmp_path / "table7_publication_info.jsonl"
    publication_jsonl.write_text(
        "\n".join(
            [
                json.dumps({"_row_number": 2, "Pubmed_id": "16643317", "Title": "Parkin study"}),
                json.dumps({"_row_number": 3, "Pubmed_id": None, "Title": "missing pmid"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "pdfs"
    pubmed_service = _FakePubMedService()
    requested_urls = []

    def fake_pdf_response(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            content=b"%PDF-1.4\nfake pdf\n%%EOF\n",
            headers={"content-type": "application/pdf"},
            request=request,
        )

    transport = httpx.MockTransport(fake_pdf_response)

    report = await fetch_publication_pdfs(
        publication_jsonl=publication_jsonl,
        output_dir=output_dir,
        pubmed_service=pubmed_service,
        transport=transport,
        limit=1,
    )

    assert report.requested_count == 1
    assert report.downloaded_count == 1
    assert report.records[0].pmid == "16643317"
    assert report.records[0].pmcid == "PMC12345"
    assert report.records[0].status == "downloaded"
    assert requested_urls == ["https://europepmc.org/articles/PMC12345?pdf=render"]
    assert (output_dir / "pdfs" / "16643317.pdf").read_bytes().startswith(b"%PDF")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["pdf_path"].endswith("16643317.pdf")


@pytest.mark.asyncio
async def test_fetch_publication_pdfs_falls_back_when_europepmc_pdf_fails(tmp_path: Path) -> None:
    publication_jsonl = tmp_path / "table7_publication_info.jsonl"
    publication_jsonl.write_text(
        json.dumps({"_row_number": 2, "Pubmed_id": "16643317", "Title": "Parkin study"}) + "\n",
        encoding="utf-8",
    )
    requested_urls = []

    def fake_pdf_response(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == "https://europepmc.org/articles/PMC12345?pdf=render":
            return httpx.Response(500, request=request)
        return httpx.Response(
            200,
            content=b"%PDF-1.4\nfallback pdf\n%%EOF\n",
            headers={"content-type": "application/pdf"},
            request=request,
        )

    report = await fetch_publication_pdfs(
        publication_jsonl=publication_jsonl,
        output_dir=tmp_path / "pdfs",
        pubmed_service=_FakePubMedService(),
        transport=httpx.MockTransport(fake_pdf_response),
        limit=1,
    )

    assert report.downloaded_count == 1
    assert requested_urls == [
        "https://europepmc.org/articles/PMC12345?pdf=render",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/pdf/",
    ]
    assert report.records[0].pdf_url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/pdf/"


@pytest.mark.asyncio
async def test_fetch_publication_pdfs_records_pubmed_lookup_errors(tmp_path: Path) -> None:
    publication_jsonl = tmp_path / "table7_publication_info.jsonl"
    publication_jsonl.write_text(
        json.dumps({"_row_number": 2, "Pubmed_id": "16643317", "Title": "Parkin study"}) + "\n",
        encoding="utf-8",
    )

    report = await fetch_publication_pdfs(
        publication_jsonl=publication_jsonl,
        output_dir=tmp_path / "pdfs",
        pubmed_service=_TimeoutPubMedService(),
        transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request)),
        limit=1,
    )

    assert report.requested_count == 1
    assert report.downloaded_count == 0
    assert report.records[0].status == "metadata_error"
    assert "ReadTimeout" in report.records[0].warning


@pytest.mark.asyncio
async def test_fetch_publication_pdfs_supports_start_offset_and_concurrency(tmp_path: Path) -> None:
    publication_jsonl = tmp_path / "table7_publication_info.jsonl"
    publication_jsonl.write_text(
        "\n".join(
            [
                json.dumps({"_row_number": 2, "Pubmed_id": "111", "Title": "first"}),
                json.dumps({"_row_number": 3, "Pubmed_id": "16643317", "Title": "second"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = await fetch_publication_pdfs(
        publication_jsonl=publication_jsonl,
        output_dir=tmp_path / "pdfs",
        pubmed_service=_FakePubMedService(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=b"%PDF-1.4\nfake pdf\n%%EOF\n",
                request=request,
            )
        ),
        start=1,
        limit=1,
        concurrency=2,
    )

    assert report.requested_count == 1
    assert report.records[0].pmid == "16643317"


class _FakeCandidate:
    pmid = "16643317"
    pmcid = "PMC12345"
    doi = "10.1000/example"
    title = "Parkin study"
    journal = "Example Journal"
    pub_date = "2005"

    @property
    def pmc_pdf_url(self) -> str:
        return "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/pdf/"


class _FakePubMedService:
    async def search_candidates(self, query: str, candidate_limit: int = 15):
        assert query == "16643317[PMID]"
        assert candidate_limit == 1
        return [_FakeCandidate()]


class _TimeoutPubMedService:
    async def search_candidates(self, query: str, candidate_limit: int = 15):
        raise httpx.ReadTimeout("metadata lookup timed out")


def _write_minimal_xlsx(path: Path) -> Path:
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="table7_publication_info" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>Pubmed_id</t></is></c>
      <c r="B1" t="inlineStr"><is><t>Title</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>16643317.0</t></is></c>
      <c r="B2" t="inlineStr"><is><t>Parkin study</t></is></c>
    </row>
    <row r="3">
      <c r="A3" t="inlineStr"><is><t>/</t></is></c>
      <c r="B3" t="inlineStr"><is><t>\\</t></is></c>
    </row>
  </sheetData>
</worksheet>""",
    }
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path
