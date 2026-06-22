"""Read and audit the Parkinson literature XLSX collection."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zipfile import ZipFile
import xml.etree.ElementTree as ET

SHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
MISSING_MARKERS = {"", "/", "\\"}
IDENTIFIER_COLUMNS = ("Pubmed_id", "Var_id", "Fam_sample_id", "Fam_id", "Sample_id", "Id")


@dataclass(frozen=True)
class WorkbookTable:
    """Normalized rows from one workbook sheet."""

    name: str
    headers: tuple[str, ...]
    rows: tuple[Mapping[str, str | None], ...]
    row_numbers: tuple[int, ...]


@dataclass(frozen=True)
class ColumnProfile:
    """Completeness profile for one column."""

    name: str
    non_empty_count: int
    sample_values: tuple[str, ...]

    def to_json_dict(self) -> Mapping[str, object]:
        """Return a stable JSON object for this column profile."""
        return {
            "name": self.name,
            "non_empty_count": self.non_empty_count,
            "sample_values": list(self.sample_values),
        }


@dataclass(frozen=True)
class SheetAudit:
    """Audit metrics for one normalized workbook sheet."""

    name: str
    data_rows: int
    column_count: int
    non_empty_counts: Mapping[str, int]
    identifier_counts: Mapping[str, int]
    duplicate_key_counts: Mapping[str, int]
    columns: tuple[ColumnProfile, ...]

    def to_json_dict(self) -> Mapping[str, object]:
        """Return a stable JSON object for this sheet audit."""
        return {
            "name": self.name,
            "data_rows": self.data_rows,
            "column_count": self.column_count,
            "non_empty_counts": dict(self.non_empty_counts),
            "identifier_counts": dict(self.identifier_counts),
            "duplicate_key_counts": dict(self.duplicate_key_counts),
            "columns": [column.to_json_dict() for column in self.columns],
        }


@dataclass(frozen=True)
class DatasetAuditReport:
    """Structural readiness report for the workbook dataset."""

    sheet_count: int
    total_data_rows: int
    sheets: tuple[SheetAudit, ...]

    def to_json_dict(self) -> Mapping[str, object]:
        """Return a stable JSON object for this dataset audit."""
        return {
            "sheet_count": self.sheet_count,
            "total_data_rows": self.total_data_rows,
            "sheets": [sheet.to_json_dict() for sheet in self.sheets],
        }


def normalize_missing(value: object) -> str | None:
    """Normalize placeholder values to None and trim real strings."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in MISSING_MARKERS else text


def normalize_pubmed_id(value: object) -> str | None:
    """Normalize PubMed IDs loaded from Excel numeric-looking cells."""
    text = normalize_missing(value)
    if text is None:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def normalize_row(headers: tuple[str, ...], values: tuple[str | None, ...]) -> Mapping[str, str | None]:
    """Normalize one workbook row into a header-keyed mapping."""
    row: dict[str, str | None] = {}
    for index, header in enumerate(headers):
        value = values[index] if index < len(values) else None
        if header == "Pubmed_id":
            row[header] = normalize_pubmed_id(value)
        else:
            row[header] = normalize_missing(value)
    return row


def load_workbook_tables(path: Path) -> Mapping[str, WorkbookTable]:
    """Load workbook sheets into normalized tables without third-party dependencies."""
    with ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet_targets = _sheet_targets(archive)
        tables: dict[str, WorkbookTable] = {}
        for sheet_name, target in sheet_targets:
            raw_rows = _load_sheet_rows(archive, target, shared_strings)
            if not raw_rows:
                tables[sheet_name] = WorkbookTable(name=sheet_name, headers=(), rows=(), row_numbers=())
                continue
            header_values = raw_rows[0][1]
            headers = tuple(str(value or "").strip() for value in header_values)
            data_rows: list[Mapping[str, str | None]] = []
            row_numbers: list[int] = []
            for row_number, values in raw_rows[1:]:
                normalized = normalize_row(headers, values)
                data_rows.append(normalized)
                row_numbers.append(row_number)
            tables[sheet_name] = WorkbookTable(
                name=sheet_name,
                headers=headers,
                rows=tuple(data_rows),
                row_numbers=tuple(row_numbers),
            )
    return tables


def build_audit_report(tables: Mapping[str, WorkbookTable]) -> DatasetAuditReport:
    """Build structural quality metrics for normalized workbook tables."""
    sheet_audits = tuple(_audit_sheet(table) for table in tables.values())
    return DatasetAuditReport(
        sheet_count=len(sheet_audits),
        total_data_rows=sum(sheet.data_rows for sheet in sheet_audits),
        sheets=sheet_audits,
    )


def _audit_sheet(table: WorkbookTable) -> SheetAudit:
    non_empty_counts: dict[str, int] = {header: 0 for header in table.headers}
    samples: dict[str, list[str]] = {header: [] for header in table.headers}
    identifier_counts: Counter[str] = Counter()
    duplicate_keys: Counter[str] = Counter()
    composite_keys: Counter[str] = Counter()

    for row in table.rows:
        key_parts = []
        for header in table.headers:
            value = row.get(header)
            if value is None:
                continue
            non_empty_counts[header] += 1
            if len(samples[header]) < 3:
                samples[header].append(value)
            if header in IDENTIFIER_COLUMNS:
                identifier_counts[header] += 1
                key_parts.append(f"{header}={value}")
        if key_parts:
            composite_keys["|".join(key_parts)] += 1

    for key, count in composite_keys.items():
        if count > 1:
            duplicate_keys[key] = count

    columns = tuple(
        ColumnProfile(
            name=header,
            non_empty_count=non_empty_counts[header],
            sample_values=tuple(samples[header]),
        )
        for header in table.headers
    )
    return SheetAudit(
        name=table.name,
        data_rows=len(table.rows),
        column_count=len(table.headers),
        non_empty_counts=non_empty_counts,
        identifier_counts=dict(identifier_counts),
        duplicate_key_counts=dict(duplicate_keys),
        columns=columns,
    )


def _load_shared_strings(archive: ZipFile) -> tuple[str, ...]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return ()
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return tuple(_text_content(item) for item in root.findall("a:si", SHEET_NS))


def _sheet_targets(archive: ZipFile) -> tuple[tuple[str, str], ...]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    id_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", REL_NS)
    }
    targets = []
    for sheet in workbook.findall(".//a:sheet", SHEET_NS):
        rel_id = sheet.attrib[REL_ID]
        target = id_to_target[rel_id]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        targets.append((sheet.attrib["name"], target))
    return tuple(targets)


def _load_sheet_rows(
    archive: ZipFile,
    target: str,
    shared_strings: tuple[str, ...],
) -> tuple[tuple[int, tuple[str | None, ...]], ...]:
    root = ET.fromstring(archive.read(target))
    rows = []
    for row in root.findall(".//a:sheetData/a:row", SHEET_NS):
        row_number = int(row.attrib.get("r", "0") or "0")
        cells: list[tuple[int, str | None]] = []
        max_index = -1
        for cell in row.findall("a:c", SHEET_NS):
            index = _column_index(cell.attrib.get("r", "A1"))
            value = _cell_value(cell, shared_strings)
            cells.append((index, value))
            max_index = max(max_index, index)
        if max_index < 0:
            continue
        values: list[str | None] = [None] * (max_index + 1)
        for index, value in cells:
            values[index] = value
        rows.append((row_number, tuple(values)))
    return tuple(rows)


def _cell_value(cell: ET.Element, shared_strings: tuple[str, ...]) -> str | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return _text_content(cell.find("a:is", SHEET_NS))
    value = cell.find("a:v", SHEET_NS)
    if value is None:
        return None
    text = value.text or ""
    if cell_type == "s":
        return shared_strings[int(text)]
    return text


def _text_content(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(text.text or "" for text in element.findall(".//a:t", SHEET_NS))


def _column_index(reference: str) -> int:
    column = "".join(character for character in reference if character.isalpha())
    number = 0
    for character in column:
        number = number * 26 + ord(character.upper()) - 64
    return number - 1
