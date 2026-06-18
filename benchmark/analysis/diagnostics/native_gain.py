"""Diagnose original-language vs translated-track evidence gain."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict, cast

DEFAULT_RETT_ROOT = Path(__file__).resolve().parents[1] / "literature_acquisition" / "downloads" / "rett"


class RawExtractionResult(TypedDict, total=False):
    """Loose shape for phase-2 dual-track extraction outputs."""

    original_result: Mapping[str, Any]
    translated_result: Mapping[str, Any]


@dataclass(frozen=True)
class NativeGainRow:
    """One document-level original-vs-translated evidence comparison."""

    path: Path
    lang: str
    document_id: str
    original_count: int
    translated_count: int
    shared_count: int
    original_only_count: int
    translated_only_count: int


@dataclass(frozen=True)
class NativeGainDiagnostics:
    """Aggregate native-gain diagnostics over available dual-track files."""

    root: Path
    requested_langs: tuple[str, ...]
    files_discovered: int
    files_analyzed: int
    rows: list[NativeGainRow]
    total_original_only: int
    total_translated_only: int
    total_shared: int
    missing_dual_track_data: bool


def _load_extraction(path: Path) -> RawExtractionResult:
    with path.open(encoding="utf-8") as file_obj:
        return cast(RawExtractionResult, json.load(file_obj))


def _evidence_items(track_result: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(track_result, Mapping):
        return []
    items = track_result.get("evidence_items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, Mapping) and item.get("status") == "found"]


def _normalize_value(value: object) -> str:
    if isinstance(value, Mapping):
        if "value" in value:
            return _normalize_value(value["value"])
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "").strip().casefold()


def _evidence_keys(items: list[Mapping[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for item in items:
        field_id = str(item.get("field_id", "")).strip()
        value = _normalize_value(item.get("value"))
        if field_id and value:
            keys.add((field_id, value))
    return keys


def _infer_lang(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return path.parent.name
    return relative.parts[0] if relative.parts else path.parent.name


def _document_id(path: Path) -> str:
    parent = path.parent
    if parent.name in {"phase_2", "preprocessed"} and parent.parent.name:
        return parent.parent.name
    return parent.name


def discover_extraction_files(root: Path) -> list[Path]:
    """Discover candidate dual-track extraction result JSON files."""
    if not root.exists():
        return []
    return sorted(root.rglob("extraction_result.json"))


def compare_dual_track_file(path: Path, lang: str | None = None, root: Path | None = None) -> NativeGainRow:
    """Compare original and translated evidence sets in one extraction result."""
    report = _load_extraction(path)
    original_keys = _evidence_keys(_evidence_items(report.get("original_result")))
    translated_keys = _evidence_keys(_evidence_items(report.get("translated_result")))
    shared = original_keys & translated_keys
    original_only = original_keys - translated_keys
    translated_only = translated_keys - original_keys
    root_path = root or path.parents[2]
    return NativeGainRow(
        path=path,
        lang=lang or _infer_lang(path, root_path),
        document_id=_document_id(path),
        original_count=len(original_keys),
        translated_count=len(translated_keys),
        shared_count=len(shared),
        original_only_count=len(original_only),
        translated_only_count=len(translated_only),
    )


def build_native_gain_diagnostics(
    root: Path = DEFAULT_RETT_ROOT,
    langs: Sequence[str] = (),
    limit: int | None = None,
) -> NativeGainDiagnostics:
    """Build original-vs-translated evidence count diagnostics."""
    requested_langs = tuple(sorted(lang for lang in langs if lang))
    files = discover_extraction_files(root)
    filtered_files = [
        path for path in files
        if not requested_langs or _infer_lang(path, root) in requested_langs
    ]
    limited_files = filtered_files[:limit] if limit is not None else filtered_files
    rows = [
        compare_dual_track_file(path, lang=_infer_lang(path, root), root=root)
        for path in limited_files
    ]
    return NativeGainDiagnostics(
        root=root,
        requested_langs=requested_langs,
        files_discovered=len(files),
        files_analyzed=len(rows),
        rows=rows,
        total_original_only=sum(row.original_only_count for row in rows),
        total_translated_only=sum(row.translated_only_count for row in rows),
        total_shared=sum(row.shared_count for row in rows),
        missing_dual_track_data=not rows,
    )


def format_native_gain_diagnostics(diagnostics: NativeGainDiagnostics) -> str:
    """Format native-gain diagnostics for terminal review."""
    langs = ",".join(diagnostics.requested_langs) if diagnostics.requested_langs else "all"
    lines = [
        f"ROOT: {diagnostics.root}",
        (
            f"langs={langs} files_discovered={diagnostics.files_discovered} "
            f"files_analyzed={diagnostics.files_analyzed}"
        ),
        (
            f"totals: original_only={diagnostics.total_original_only} "
            f"translated_only={diagnostics.total_translated_only} "
            f"shared={diagnostics.total_shared}"
        ),
    ]
    for row in diagnostics.rows:
        lines.append(
            f"  {row.lang}/{row.document_id}: "
            f"original={row.original_count} translated={row.translated_count} "
            f"shared={row.shared_count} original_only={row.original_only_count} "
            f"translated_only={row.translated_only_count}"
        )
    if diagnostics.missing_dual_track_data:
        lines.append(
            "WARNING: native-gain metrics are unavailable because this root has missing dual-track extraction_result.json files."
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_RETT_ROOT)
    parser.add_argument("--langs", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    diagnostics = build_native_gain_diagnostics(args.root, tuple(args.langs), args.limit)
    print(format_native_gain_diagnostics(diagnostics))


if __name__ == "__main__":
    main()
