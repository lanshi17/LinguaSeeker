"""Conservative AI-assisted source-visible drafts for fused-75 adjudication."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_ADJUDICATOR = "ai-assisted-reviewer"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AssistedReviewResult:
    """Summary for one AI-assisted adjudication pass."""

    processed_entries: int
    source_visible_labels: int
    unchanged_labels: int
    missing_sources: tuple[Path, ...]


@dataclass(frozen=True)
class AssistedMatch:
    """One high-confidence source-visible match."""

    quote: str
    location: str
    rationale: str


def assist_adjudication_directory(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    project_root: Path = _PROJECT_ROOT,
    adjudicator: str = _DEFAULT_ADJUDICATOR,
) -> AssistedReviewResult:
    """Fill high-confidence source-visible decisions without completing entries."""
    processed_entries = 0
    source_visible_labels = 0
    unchanged_labels = 0
    missing_sources: list[Path] = []

    for path in _adjudication_paths(adjudication_root):
        adjudication = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
        source_path = _resolve_project_path(adjudication.source_path, project_root)
        expected_path = _resolve_project_path(adjudication.expected_path, project_root)
        if not source_path.exists():
            missing_sources.append(source_path)
            continue
        source_text = source_path.read_text(encoding="utf-8")
        expected_payload = _load_json(expected_path) if expected_path.exists() else {}
        context = _entry_context(adjudication, expected_payload)

        labels: list[Fused75FieldAdjudication] = []
        for label in adjudication.labels:
            if label.visibility is not None and label.adjudicator != adjudicator:
                unchanged_labels += 1
                labels.append(label)
                continue
            match = _assist_label(label, source_text, source_path, context)
            if match is None:
                unchanged_labels += 1
                labels.append(_clear_machine_label(label, adjudicator))
                continue
            source_visible_labels += 1
            labels.append(
                label.model_copy(
                    update={
                        "visibility": "source_visible",
                        "source_quote": match.quote,
                        "source_location": match.location,
                        "adjudicator": adjudicator,
                        "notes": match.rationale,
                    }
                )
            )

        updated = adjudication.model_copy(update={"is_complete": False, "labels": tuple(labels)})
        _write_adjudication(updated, path)
        processed_entries += 1

    return AssistedReviewResult(
        processed_entries=processed_entries,
        source_visible_labels=source_visible_labels,
        unchanged_labels=unchanged_labels,
        missing_sources=tuple(missing_sources),
    )


def _assist_label(
    label: Fused75FieldAdjudication,
    source_text: str,
    source_path: Path,
    context: Mapping[str, str],
) -> AssistedMatch | None:
    if label.field_id == "A.gene_disease_relationship" and label.expected_value.casefold() == "causative":
        return _find_relationship_match(source_text, source_path, context)
    if label.field_id == "B.mode_of_inheritance_reported":
        return _find_moi_match(source_text, source_path, label.expected_value)
    if label.field_id in {"A.variant_hgvs_c", "A.variant_hgvs_p"}:
        return _find_variant_match(source_text, source_path, label.expected_value)
    if label.field_id == "J.clinvar_assertion":
        return _find_classification_match(source_text, source_path, label.expected_value)
    if label.field_id == "B.disease_diagnosis":
        return _find_fuzzy_phrase_match(source_text, source_path, label.expected_value, "disease phrase overlap")
    if label.field_id == "A.variant_type":
        return _find_fuzzy_phrase_match(source_text, source_path, label.expected_value, "variant type phrase")
    return None


def _entry_context(adjudication: Fused75EntryAdjudication, expected_payload: Mapping[str, Any]) -> dict[str, str]:
    clingen = expected_payload.get("clingen")
    clingen_mapping = clingen if isinstance(clingen, Mapping) else {}
    gene = _first_text(clingen_mapping.get("gene_symbol"), _label_value(adjudication, "A.gene_symbol"))
    disease = _first_text(clingen_mapping.get("disease_label"), _label_value(adjudication, "B.disease_diagnosis"))
    return {"gene": gene, "disease": disease}


def _label_value(adjudication: Fused75EntryAdjudication, field_id: str) -> str:
    for label in adjudication.labels:
        if label.field_id == field_id:
            return label.expected_value
    return ""


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _find_relationship_match(source_text: str, source_path: Path, context: Mapping[str, str]) -> AssistedMatch | None:
    gene = context.get("gene", "")
    disease = context.get("disease", "")
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        folded = line.casefold()
        if gene and gene.casefold() not in folded:
            continue
        if disease and not _tokens_present(disease, folded, min_tokens=1):
            continue
        if any(pattern in folded for pattern in ("caused by", "results from", "disease-causing")):
            return _match(line, source_path, line_number, "AI-assisted causative relationship phrase")
    return None


def _find_moi_match(source_text: str, source_path: Path, expected_value: str) -> AssistedMatch | None:
    phrases = {
        "AR": ("autosomal recessive", "recessive disorder"),
        "AD": ("autosomal dominant",),
        "XL": ("x-linked", "x linked", "x-linked recessive", "x-linked dominant"),
        "XD": ("x-linked dominant", "x linked dominant"),
    }.get(expected_value.upper(), ())
    if not phrases:
        return None
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        folded = line.casefold()
        if any(phrase in folded for phrase in phrases):
            return _match(line, source_path, line_number, f"AI-assisted MOI phrase for {expected_value}")
    return None


def _find_variant_match(source_text: str, source_path: Path, expected_value: str) -> AssistedMatch | None:
    terms = _variant_terms(expected_value)
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        folded = _normalize_variant_text(line)
        if any(term and term in folded for term in terms):
            return _match(line, source_path, line_number, "AI-assisted normalized variant mention")
    return None


def _find_classification_match(source_text: str, source_path: Path, expected_value: str) -> AssistedMatch | None:
    expected = expected_value.casefold()
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        folded = line.casefold()
        if expected in folded and any(term in folded for term in ("pathogenic", "classification", "classified")):
            return _match(line, source_path, line_number, "AI-assisted classification phrase")
    return None


def _find_fuzzy_phrase_match(
    source_text: str,
    source_path: Path,
    expected_value: str,
    rationale: str,
) -> AssistedMatch | None:
    tokens = _important_tokens(expected_value)
    if not tokens:
        return None
    min_tokens = max(1, min(len(tokens), 3))
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        if _tokens_present(expected_value, line.casefold(), min_tokens=min_tokens):
            return _match(line, source_path, line_number, f"AI-assisted {rationale}")
    return None


def _tokens_present(value: str, folded_line: str, *, min_tokens: int) -> bool:
    tokens = _important_tokens(value)
    return sum(1 for token in tokens if token in folded_line) >= min_tokens


def _important_tokens(value: str) -> tuple[str, ...]:
    stop = {"and", "or", "with", "without", "due", "to", "related", "disease", "syndrome"}
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return tuple(token for token in tokens if len(token) > 2 and token not in stop)


def _variant_terms(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    no_prefix = re.sub(r"^[cpgnmr]\.", "", stripped, flags=re.IGNORECASE)
    compact = _normalize_variant_text(stripped)
    compact_no_prefix = _normalize_variant_text(no_prefix)
    return tuple({compact, compact_no_prefix})


def _normalize_variant_text(value: str) -> str:
    return re.sub(r"[^a-z0-9>\[\]+*-]", "", value.casefold())


def _match(line: str, source_path: Path, line_number: int, rationale: str) -> AssistedMatch:
    quote = " ".join(line.strip().split())
    if len(quote) > 500:
        quote = quote[:500].strip()
    return AssistedMatch(quote=quote, location=f"{source_path}:{line_number}", rationale=rationale)


def _adjudication_paths(adjudication_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for split in ("dev", "test") for path in (adjudication_root / split).glob("*.json")))


def _resolve_project_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def _clear_machine_label(label: Fused75FieldAdjudication, adjudicator: str) -> Fused75FieldAdjudication:
    if label.adjudicator != adjudicator:
        return label
    return label.model_copy(
        update={
            "visibility": None,
            "source_quote": None,
            "source_location": None,
            "adjudicator": None,
            "notes": None,
        }
    )


def _write_adjudication(adjudication: Fused75EntryAdjudication, path: Path) -> None:
    path.write_text(
        json.dumps(adjudication.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    parser.add_argument("--project-root", type=Path, default=_PROJECT_ROOT)
    parser.add_argument("--adjudicator", default=_DEFAULT_ADJUDICATOR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run conservative AI-assisted source-visible drafting."""
    args = _parse_args(argv)
    result = assist_adjudication_directory(
        adjudication_root=args.adjudication_root,
        project_root=args.project_root,
        adjudicator=args.adjudicator,
    )
    print(
        json.dumps(
            {
                "processed_entries": result.processed_entries,
                "source_visible_labels": result.source_visible_labels,
                "unchanged_labels": result.unchanged_labels,
                "missing_sources": [str(path) for path in result.missing_sources],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
