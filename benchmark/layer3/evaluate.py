"""Layer 3 evaluation: submit articles to pipeline and compare against ClinGen ground truth.

Flow:
1. For each ground truth entry with source.md:
   a. Convert markdown to PDF (fpdf2)
   b. Submit PDF to pipeline API
   c. Wait for completion
   d. Query extracted evidence from PG
   e. Compare against ground truth expected fields
2. Aggregate metrics: Precision, Recall, F1 per field type
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
from typing import Any
import time
import unicodedata
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx
import yaml
from loguru import logger
from sqlalchemy import select, text

from benchmark.pipeline.evidence_metrics import query_evidence_metrics
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.models import EvidenceEntityBinding, NormalizedEntity, RunEvidenceItem

try:
    from benchmark.layer3.mondo_hierarchy import MondoHierarchy
except ImportError:
    MondoHierarchy = None  # type: ignore[assignment,misc]

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

POLL_INTERVAL_S = 5.0
MAX_POLL_ATTEMPTS = 360  # 30 min max per entry
TERMINAL_STATUSES = {"awaiting_review", "completed", "failed"}


def _run_id_from_status_url(status_url: str) -> str | None:
    """Extract a pipeline run ID from the canonical status URL."""
    match = re.search(r"/runs/([^/]+)/status$", status_url)
    return match.group(1) if match else None


async def preflight_database_connection(session_factory) -> None:  # noqa: ANN001
    """Verify evaluator DB credentials before submitting long-running pipeline jobs."""
    try:
        async with session_factory() as session:
            row = (
                await session.execute(text("select current_user, current_database()"))
            ).one()
    except Exception as exc:
        raise RuntimeError(
            "Layer 3 database preflight failed before pipeline submission. "
            "Check POSTGRES_USER/POSTGRES_PASSWORD and worktree vault/env setup."
        ) from exc

    logger.info("DB preflight OK: user={} database={}", row[0], row[1])


# ── PDF generation ─────────────────────────────────────────────────────

def _sanitize_for_pdf(text: str) -> str:
    """Remove characters that can't be encoded in latin-1."""
    # Replace common Unicode chars with ASCII equivalents
    replacements = {
        "–": "-", "—": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...", "°": "deg",
        "µ": "u", "×": "x", "±": "+/-", "≤": "<=",
        "≥": ">=", "α": "alpha", "β": "beta", "γ": "gamma",
        "→": "->", "←": "<-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode to latin-1, replacing unknown chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


def markdown_to_pdf_bytes(md_text: str, title: str = "") -> bytes:
    """Convert markdown text to PDF bytes using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=10)

    if title:
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(0, 8, _sanitize_for_pdf(title[:200]))
        pdf.ln(5)
        pdf.set_font("Helvetica", size=10)

    lines = md_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        # Truncate very long lines
        if len(line) > 2000:
            line = line[:2000] + "..."
        text = _sanitize_for_pdf(line)
        if not text.strip():
            continue
        try:
            if line.startswith("## "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6, text[3:] if len(text) > 3 else text)
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("# "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, text[2:] if len(text) > 2 else text)
                pdf.set_font("Helvetica", size=10)
            else:
                pdf.multi_cell(0, 5, text)
        except Exception:
            # Skip problematic lines
            continue

    return bytes(pdf.output())


# ── Comparison ─────────────────────────────────────────────────────────

_PUNCT_TRANSLATION = str.maketrans({
    "‐": "-",  # ‐ hyphen
    "‑": "-",  # ‑ non-breaking hyphen
    "‒": "-",  # ‒ figure dash
    "–": "-",  # – en dash
    "—": "-",  # — em dash
    "―": "-",  # ― horizontal bar
    "−": "-",  # − minus sign
    "－": "-",  # － fullwidth hyphen-minus
    "‘": "'",  # ' left single quotation mark
    "’": "'",  # ' right single quotation mark
    "“": '"',  # " left double quotation mark
    "”": '"',  # " right double quotation mark
})
_NORMALIZE_CANDIDATE_PUNCT = str.maketrans({
    ",": " ",
    ";": " ",
    ":": " ",
    "，": " ",
    "；": " ",
    "：": " ",
})


def normalize_comparison_text(value: str) -> str:
    """Normalize harmless typography differences for benchmark matching."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(_PUNCT_TRANSLATION)
    normalized = normalized.translate(_NORMALIZE_CANDIDATE_PUNCT)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass
class FieldMatch:
    """Result of matching one expected field against extracted evidence."""

    field_id: str
    expected_value: str
    matched: bool
    extracted_value: str | None = None
    extracted_confidence: float | None = None
    source_span: dict[str, object] | None = None
    match_type: str = "none"  # exact, fuzzy, none
    extra_found_values: list[str] = field(default_factory=list)
    best_score: float | None = None
    source_score: float | None = None
    confidence_score: float | None = None
    agreement_score: float | None = None
    status_score: float | None = None
    verifier_support_score: float | None = None
    target_specificity_score: float | None = None
    contradiction_penalty: float | None = None
    accepted_track: str | None = None
    normalized_value: str | None = None


@dataclass
class EntryMetrics:
    """Metrics for one ground truth entry evaluation."""

    entry_id: str
    gene_symbol: str
    classification: str
    language: str
    moi: str = ""
    run_id: str | None = None
    status_url: str | None = None
    pipeline_status: str = "pending"
    error_message: str | None = None
    last_pipeline_status: str | None = None
    last_current_phase: str | None = None
    duration_s: float = 0.0
    field_matches: list[FieldMatch] = field(default_factory=list)
    entity_matches: dict[str, bool] = field(default_factory=dict)
    standardization_accuracy: float = 0.0
    track_consistency: float = 0.0
    evidence_count: int = 0
    found_rate: float = 0.0
    grounding_rate: float = 0.0


def fuzzy_match_value(expected: str, extracted: str) -> bool:
    """Fuzzy value matching with word-overlap for disease names."""
    if not expected or not extracted:
        return False
    exp_norm = normalize_comparison_text(expected)
    ext_norm = normalize_comparison_text(extracted)
    exp_lower = exp_norm.lower()
    ext_lower = ext_norm.lower()
    # Exact match
    if exp_lower == ext_lower:
        return True
    # Substring containment
    if exp_lower in ext_lower or ext_lower in exp_lower:
        return True
    # Gene symbol exact match (case-sensitive)
    if exp_norm == ext_norm:
        return True
    # Word-overlap matching for disease names
    # e.g., "Charcot-Marie-Tooth disease" matches "Charcot-Marie-Tooth disease axonal type 2N"
    exp_words = set(re.split(r"[\s\-]+", exp_lower))
    ext_words = set(re.split(r"[\s\-]+", ext_lower))
    # Remove common stop words
    stop_words = {"disease", "syndrome", "disorder", "type", "the", "a", "an", "of", "due", "to", "with", "and", "or"}
    exp_words -= stop_words
    ext_words -= stop_words
    if exp_words and ext_words:
        overlap = exp_words & ext_words
        # If >60% of expected words are found in extracted, consider it a match
        if len(overlap) / len(exp_words) >= 0.6:
            return True
    return False


# Fields that benefit from ontology ancestry matching
_DISEASE_FIELDS = {"B.disease_diagnosis", "B.disease_phenotype"}


def compare_evidence(
    expected_fields: list[dict],
    extracted_items: list[dict],
    mondo: Any | None = None,
    expected_standardization: dict[str, str] | None = None,
) -> list[FieldMatch]:
    """Compare expected evidence fields against extracted items.

    When ``mondo`` is provided and a disease field fails fuzzy matching,
    falls back to MONDO ancestry checking: the extracted disease label
    is looked up in MONDO and checked against the expected MONDO ID's
    ancestor chain.
    """
    matches: list[FieldMatch] = []
    expected_mondo_id = (expected_standardization or {}).get("disease", "")

    for expected in expected_fields:
        field_id = expected["field_id"]
        expected_value = str(expected.get("value", ""))

        # Find matching extracted items
        candidates = [
            item for item in extracted_items
            if item.get("field_id") == field_id and item.get("status") == "found"
        ]

        if not candidates:
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                match_type="missing",
            ))
            continue

        # Check each candidate for value match
        best_match: FieldMatch | None = None
        for cand in candidates:
            extracted_value = str(cand.get("value", ""))
            confidence = cand.get("confidence", 0.0)
            source_span = cand.get("source_span") if isinstance(cand.get("source_span"), dict) else None

            expected_norm = normalize_comparison_text(expected_value).lower()
            extracted_norm = normalize_comparison_text(extracted_value).lower()
            if expected_norm == extracted_norm:
                match_type = "exact"
            elif fuzzy_match_value(expected_value, extracted_value):
                match_type = "fuzzy"
            else:
                continue

            candidate_match = FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=True,
                extracted_value=extracted_value,
                extracted_confidence=confidence,
                source_span=source_span,
                match_type=match_type,
                **_score_components(cand),
            )
            if best_match is None or (match_type == "exact" and best_match.match_type != "exact"):
                best_match = candidate_match

        # Ontology ancestry fallback for disease fields
        if not best_match and mondo and field_id in _DISEASE_FIELDS and expected_mondo_id:
            for cand in candidates:
                extracted_value = str(cand.get("value", ""))
                if mondo.is_label_descendant_of(extracted_value, expected_mondo_id):
                    best_match = FieldMatch(
                        field_id=field_id,
                        expected_value=expected_value,
                        matched=True,
                        extracted_value=extracted_value,
                        extracted_confidence=cand.get("confidence", 0.0),
                        source_span=cand.get("source_span") if isinstance(cand.get("source_span"), dict) else None,
                        match_type="ontology_ancestor",
                        **_score_components(cand),
                    )
                    break

        if best_match:
            extra_values: list[str] = []
            seen_extra_values: set[str] = set()
            for cand in candidates:
                value = str(cand.get("value", ""))
                normalized_value = normalize_comparison_text(value).lower()
                if normalized_value in seen_extra_values:
                    continue
                if value != best_match.extracted_value and not fuzzy_match_value(expected_value, value):
                    seen_extra_values.add(normalized_value)
                    extra_values.append(value)
            matches.append(replace(best_match, extra_found_values=extra_values))
        else:
            # Found field but wrong value
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                extracted_value=str(candidates[0].get("value", "")),
                extracted_confidence=candidates[0].get("confidence", 0.0),
                source_span=candidates[0].get("source_span") if isinstance(candidates[0].get("source_span"), dict) else None,
                match_type="wrong_value",
                **_score_components(candidates[0]),
            ))

    return matches


def _score_components(candidate: dict) -> dict[str, float | str | None]:
    """Copy optional contextual reconcile score components from a benchmark candidate."""
    return {
        "best_score": _optional_float(candidate.get("best_score")),
        "source_score": _optional_float(candidate.get("source_score")),
        "confidence_score": _optional_float(candidate.get("confidence_score")),
        "agreement_score": _optional_float(candidate.get("agreement_score")),
        "status_score": _optional_float(candidate.get("status_score")),
        "verifier_support_score": _optional_float(candidate.get("verifier_support_score")),
        "target_specificity_score": _optional_float(candidate.get("target_specificity_score")),
        "contradiction_penalty": _optional_float(candidate.get("contradiction_penalty")),
        "accepted_track": _optional_string(candidate.get("accepted_track")),
        "normalized_value": _optional_string(candidate.get("normalized_value")),
    }


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def mark_expected_fields_missing(
    metrics: EntryMetrics,
    entry: dict,
    mondo: Any | None = None,
) -> None:
    """Populate missing field matches when no usable extraction result exists."""
    metrics.field_matches = compare_evidence(
        entry.get("expected_evidence", []),
        [],
        mondo=mondo,
        expected_standardization=entry.get("expected_standardization"),
    )


async def compare_entity_standardization(
    session,
    run_id: str,
    expected_standardization: dict[str, str],
) -> dict[str, dict]:
    """Compare entity standardization against expected external IDs.

    Queries evidence_entity_bindings + normalized_entities to check
    whether the pipeline resolved gene/disease to the correct HGNC/MONDO IDs.
    """
    stmt = (
        select(
            EvidenceEntityBinding.entity_type,
            NormalizedEntity.external_id,
            NormalizedEntity.standardization_status,
            NormalizedEntity.display_name,
        )
        .join(NormalizedEntity, EvidenceEntityBinding.entity_id == NormalizedEntity.entity_id)
        .where(EvidenceEntityBinding.run_evidence_item_id.in_(
            select(RunEvidenceItem.run_evidence_item_id)
            .where(RunEvidenceItem.processing_run_id == uuid.UUID(run_id))
        ))
        .distinct()
    )
    rows = (await session.execute(stmt)).all()

    results: dict[str, dict] = {}
    for entity_type, expected_id in expected_standardization.items():
        matching = [r for r in rows if r.entity_type == entity_type]
        matched = any(r.external_id == expected_id for r in matching)
        best = next((r for r in matching if r.external_id == expected_id), None)
        results[entity_type] = {
            "matched": matched,
            "expected_id": expected_id,
            "actual_id": best.external_id if best else (matching[0].external_id if matching else None),
            "status": best.standardization_status if best else (matching[0].standardization_status if matching else "not_found"),
        }
    return results


async def compare_track_consistency(
    session,
    run_id: str,
) -> dict:
    """Compare original vs translated track field values for consistency."""
    stmt = (
        select(
            RunEvidenceItem.field_id,
            RunEvidenceItem.track,
            RunEvidenceItem.value,
            RunEvidenceItem.status,
        )
        .where(
            RunEvidenceItem.processing_run_id == uuid.UUID(run_id),
            RunEvidenceItem.status == "found",
        )
    )
    rows = (await session.execute(stmt)).all()

    by_field: dict[str, dict[str, str]] = {}
    for r in rows:
        if r.field_id not in by_field:
            by_field[r.field_id] = {}
        if r.track not in by_field[r.field_id]:
            by_field[r.field_id][r.track] = str(r.value)

    compared = []
    matched = 0
    total = 0
    for fid, tracks in by_field.items():
        if "original" in tracks and "translated" in tracks:
            is_match = fuzzy_match_value(tracks["original"], tracks["translated"])
            compared.append({
                "field_id": fid,
                "original": tracks["original"],
                "translated": tracks["translated"],
                "match": is_match,
            })
            total += 1
            if is_match:
                matched += 1

    return {
        "items": compared,
        "consistency": matched / total if total > 0 else 0.0,
        "total_compared": total,
        "matched": matched,
    }


# ── Pipeline interaction ───────────────────────────────────────────────

async def submit_and_poll(
    client: httpx.AsyncClient,
    base_url: str,
    pdf_bytes: bytes | None,
    filename: str,
    pre_parsed_markdown: str | None = None,
    extraction_target: dict | None = None,
) -> dict:
    """Submit document and poll until completion.

    Uses pre_parsed_markdown when provided (bypasses MinerU Phase 1).
    Falls back to PDF submission via content_base64 otherwise.
    """
    payload: dict = {
        "source_type": "local",
        "mode": "full",
        "filename": filename,
    }
    if pre_parsed_markdown:
        payload["pre_parsed_markdown"] = pre_parsed_markdown
    if pdf_bytes:
        payload["content_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
    if extraction_target is not None:
        payload["target"] = extraction_target

    resp = await client.post(
        f"{base_url}/api/v1/pipeline/run",
        json=payload,
        timeout=60.0,
    )
    if resp.status_code == 409:
        # Stale in-memory dedup — retry with unique filename suffix
        import time as _time
        unique_name = filename.rsplit(".", 1)
        unique_name = f"{unique_name[0]}_{int(_time.time())}.{unique_name[1]}" if len(unique_name) == 2 else f"{filename}_{int(_time.time())}"
        payload["filename"] = unique_name
        resp = await client.post(
            f"{base_url}/api/v1/pipeline/run",
            json=payload,
            timeout=60.0,
        )
    resp.raise_for_status()
    data = resp.json()
    status_url = data["status_url"]
    run_id = data.get("processing_run_id") or _run_id_from_status_url(status_url)
    source_document_id = data.get("source_document_id")
    last_status: dict[str, Any] | None = None

    # Poll
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            resp = await client.get(f"{base_url}{status_url}", timeout=30.0)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            status_data = resp.json()
            if run_id and not status_data.get("processing_run_id"):
                status_data["processing_run_id"] = run_id
            if source_document_id and not status_data.get("source_document_id"):
                status_data["source_document_id"] = source_document_id
            status_data["status_url"] = status_url
            last_status = status_data
            ps = status_data.get("pipeline_status", "")
            if ps in TERMINAL_STATUSES:
                return status_data
        except Exception:
            continue

    return {
        "pipeline_status": "timeout",
        "error_message": "Poll timed out",
        "processing_run_id": run_id,
        "source_document_id": source_document_id,
        "status_url": status_url,
        "last_status": last_status,
    }


def load_proxy() -> str | None:
    config_path = Path(__file__).resolve().parent.parent.parent / "backend" / "config" / "environments" / "development.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        proxy = cfg.get("network", {}).get("proxy", "")
        if proxy:
            # Check if proxy is reachable before returning it
            import socket
            from urllib.parse import urlparse
            try:
                parsed = urlparse(proxy)
                host = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                sock.close()
                if result != 0:
                    logger.warning("Proxy {} is not reachable, skipping", proxy)
                    return None
            except Exception:
                return None
        return proxy
    return None


# ── Main evaluation ────────────────────────────────────────────────────

async def evaluate_one(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict,
    sf,
    semaphore: asyncio.Semaphore,
    mondo: Any | None = None,
) -> EntryMetrics:
    """Evaluate one ground truth entry."""
    entry_id = entry["entry_id"]
    gene = entry["gene_symbol"]
    classification = entry.get("classification", "")
    moi = entry.get("moi", "")

    metrics = EntryMetrics(
        entry_id=entry_id,
        gene_symbol=gene,
        classification=classification,
        language="en",
        moi=moi,
    )

    # Check for source text
    source_path = GROUND_TRUTH_DIR / entry_id / "source.md"
    if not source_path.exists():
        metrics.pipeline_status = "no_source"
        mark_expected_fields_missing(metrics, entry, mondo=mondo)
        return metrics

    md_text = source_path.read_text(encoding="utf-8")
    if len(md_text) < 100:
        metrics.pipeline_status = "source_too_small"
        mark_expected_fields_missing(metrics, entry, mondo=mondo)
        return metrics

    # Check for preprocessed Phase 1+2 data
    preprocessed_path = GROUND_TRUTH_DIR / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    use_preprocessed = preprocessed_path.exists()

    if use_preprocessed:
        # Load preprocessed extraction results directly (skip pipeline)
        logger.info("[{}] Using preprocessed Phase 1+2 data", entry_id)
        t0 = time.time()
        try:
            with open(preprocessed_path) as f:
                extraction_data = json.load(f)

            # Extract evidence items from both tracks
            extracted_items = []
            original_items = []
            translated_items = []
            for track_key, track_list in [("original_result", original_items), ("translated_result", translated_items)]:
                track_data = extraction_data.get(track_key, {})
                for item in track_data.get("evidence_items", []):
                    extracted_item = {
                        "field_id": item.get("field_id", ""),
                        "status": item.get("status", ""),
                        "value": item.get("value", ""),
                        "confidence": float(item.get("confidence", 0) or 0),
                    }
                    extracted_items.append(extracted_item)
                    track_list.append(extracted_item)

            metrics.pipeline_status = "preprocessed"
            metrics.evidence_count = len(extracted_items)
            found_count = sum(1 for i in extracted_items if i["status"] == "found")
            metrics.found_rate = found_count / len(extracted_items) if extracted_items else 0.0

            # Compare evidence
            metrics.field_matches = compare_evidence(
                entry.get("expected_evidence", []),
                extracted_items,
                mondo=mondo,
                expected_standardization=entry.get("expected_standardization"),
            )

            # Track consistency from preprocessed data
            orig_by_field = {i["field_id"]: str(i["value"]) for i in original_items if i["status"] == "found"}
            trans_by_field = {i["field_id"]: str(i["value"]) for i in translated_items if i["status"] == "found"}
            common_fields = set(orig_by_field.keys()) & set(trans_by_field.keys())
            if common_fields:
                matched = sum(1 for f in common_fields if fuzzy_match_value(orig_by_field[f], trans_by_field[f]))
                metrics.track_consistency = matched / len(common_fields)

            # Entity standardization: not available from preprocessed data
            metrics.standardization_accuracy = 0.0

            metrics.duration_s = round(time.time() - t0, 2)
            logger.info("[{}] Preprocessed evaluation complete: {}/{} fields matched",
                        entry_id, sum(1 for f in metrics.field_matches if f.matched), len(metrics.field_matches))

        except Exception as e:
            logger.error("[{}] Preprocessed evaluation failed: {}", entry_id, e)
            metrics.pipeline_status = "preprocess_error"
            metrics.error_message = str(e)
            mark_expected_fields_missing(metrics, entry, mondo=mondo)

        return metrics

    # Submit pre-parsed markdown directly (bypasses MinerU Phase 1)
    extraction_target = {
        "gene_symbol": entry["gene_symbol"],
        "disease_name": entry["disease_label"],
        "variant_hgvs_p": "",
        "clingen_entry_id": entry_id,
    }
    async with semaphore:
        t0 = time.time()
        try:
            status_data = await submit_and_poll(
                client, base_url,
                pdf_bytes=None,
                filename=f"{entry_id}.md",
                pre_parsed_markdown=md_text,
                extraction_target=extraction_target,
            )
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = status_data.get("pipeline_status", "unknown")
            metrics.run_id = status_data.get("processing_run_id")
            metrics.status_url = status_data.get("status_url")
            metrics.error_message = status_data.get("error_message")
            last_status = status_data.get("last_status")
            if isinstance(last_status, dict):
                metrics.last_pipeline_status = last_status.get("pipeline_status")
                metrics.last_current_phase = last_status.get("current_phase")

            if metrics.pipeline_status in ("awaiting_review", "completed"):
                run_id = metrics.run_id
                if not run_id:
                    raise RuntimeError("Pipeline completed without processing_run_id")

                # Query evidence metrics from PG
                try:
                    ev_metrics = await query_evidence_metrics(sf, run_id)
                    metrics.evidence_count = ev_metrics.run_evidence_count
                    metrics.found_rate = ev_metrics.found_rate
                    metrics.grounding_rate = ev_metrics.source_grounding.grounding_rate

                    # Get detailed evidence items for comparison
                    async with sf() as session:
                        stmt = select(
                            RunEvidenceItem.field_id,
                            RunEvidenceItem.status,
                            RunEvidenceItem.value,
                            RunEvidenceItem.confidence,
                            RunEvidenceItem.source_span,
                        ).where(RunEvidenceItem.processing_run_id == uuid.UUID(run_id))
                        rows = (await session.execute(stmt)).all()
                        extracted_items = [
                            {
                                "field_id": r.field_id,
                                "status": r.status,
                                "value": r.value,
                                "confidence": float(r.confidence) if r.confidence else 0.0,
                                "source_span": r.source_span,
                            }
                            for r in rows
                        ]

                    # Compare
                    metrics.field_matches = compare_evidence(
                        entry.get("expected_evidence", []),
                        extracted_items,
                        mondo=mondo,
                        expected_standardization=entry.get("expected_standardization"),
                    )

                    # Entity standardization comparison
                    async with sf() as session:
                        metrics.entity_matches = await compare_entity_standardization(
                            session, run_id, entry.get("expected_standardization", {}),
                        )
                        entity_total = len(metrics.entity_matches)
                        entity_matched = sum(1 for v in metrics.entity_matches.values() if v.get("matched"))
                        metrics.standardization_accuracy = (
                            entity_matched / entity_total if entity_total > 0 else 0.0
                        )

                        # Track consistency (original vs translated)
                        track_result = await compare_track_consistency(session, run_id)
                        metrics.track_consistency = track_result.get("consistency", 0.0)

                except Exception as e:
                    logger.warning("[{}] Evidence query failed: {}", entry_id, e)
                    mark_expected_fields_missing(metrics, entry, mondo=mondo)
            else:
                mark_expected_fields_missing(metrics, entry, mondo=mondo)

        except Exception as e:
            metrics.duration_s = round(time.time() - t0, 2)
            metrics.pipeline_status = "error"
            metrics.error_message = str(e)
            mark_expected_fields_missing(metrics, entry, mondo=mondo)
            logger.error("[{}] Pipeline error: {}", entry_id, e)

    return metrics


def _false_positive_count(metrics_list: list[EntryMetrics]) -> int:
    wrong_values = sum(
        1 for m in metrics_list for f in m.field_matches
        if f.match_type == "wrong_value"
    )
    over_extracted = sum(
        len(f.extra_found_values)
        for m in metrics_list
        for f in m.field_matches
    )
    return wrong_values + over_extracted


def _over_extraction_count(metrics_list: list[EntryMetrics]) -> int:
    return sum(
        len(f.extra_found_values)
        for m in metrics_list
        for f in m.field_matches
    )


def compute_aggregate_metrics(all_metrics: list[EntryMetrics]) -> dict:
    """Compute aggregate P/R/F1 from per-entry metrics."""
    # Field-level P/R/F1
    tp = sum(1 for m in all_metrics for f in m.field_matches if f.matched)
    fp = _false_positive_count(all_metrics)
    fn = sum(1 for m in all_metrics for f in m.field_matches if f.match_type in ("missing", "none"))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Per-field-type breakdown
    by_field: dict[str, dict] = {}
    for m in all_metrics:
        for f in m.field_matches:
            if f.field_id not in by_field:
                by_field[f.field_id] = {"tp": 0, "fp": 0, "fn": 0, "over_extractions": 0}
            if f.matched:
                by_field[f.field_id]["tp"] += 1
            elif f.match_type == "wrong_value":
                by_field[f.field_id]["fp"] += 1
            else:
                by_field[f.field_id]["fn"] += 1
            by_field[f.field_id]["fp"] += len(f.extra_found_values)
            by_field[f.field_id]["over_extractions"] += len(f.extra_found_values)

    field_f1 = {}
    for fid, counts in by_field.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) > 0 else 0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        field_f1[fid] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "over_extractions": counts["over_extractions"],
        }

    # By classification
    by_cls: dict[str, list] = {}
    for m in all_metrics:
        by_cls.setdefault(m.classification, []).append(m)

    cls_metrics = {}
    for cls, metrics_list in by_cls.items():
        cls_tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        cls_fp = _false_positive_count(metrics_list)
        cls_fn = sum(1 for m in metrics_list for f in m.field_matches if f.match_type in ("missing", "none"))
        cls_p = cls_tp / (cls_tp + cls_fp) if (cls_tp + cls_fp) > 0 else 0
        cls_r = cls_tp / (cls_tp + cls_fn) if (cls_tp + cls_fn) > 0 else 0
        cls_f1 = 2 * cls_p * cls_r / (cls_p + cls_r) if (cls_p + cls_r) > 0 else 0
        cls_metrics[cls] = {
            "count": len(metrics_list),
            "precision": round(cls_p, 4),
            "recall": round(cls_r, 4),
            "f1": round(cls_f1, 4),
            "over_extractions": _over_extraction_count(metrics_list),
        }

    # Entity standardization accuracy
    std_values = [m.standardization_accuracy for m in all_metrics if m.entity_matches]
    entity_standardization_accuracy = (
        sum(std_values) / len(std_values) if std_values else 0.0
    )

    # Per-entity-type accuracy
    by_entity_type: dict[str, dict] = {}
    for m in all_metrics:
        for etype, ematch in m.entity_matches.items():
            if etype not in by_entity_type:
                by_entity_type[etype] = {"matched": 0, "total": 0}
            by_entity_type[etype]["total"] += 1
            if ematch.get("matched"):
                by_entity_type[etype]["matched"] += 1
    entity_accuracy_by_type = {
        etype: round(v["matched"] / v["total"], 4) if v["total"] > 0 else 0.0
        for etype, v in by_entity_type.items()
    }

    # Track consistency (original vs translated)
    tc_values = [m.track_consistency for m in all_metrics if m.track_consistency > 0]
    cross_lingual_consistency = (
        sum(tc_values) / len(tc_values) if tc_values else 0.0
    )

    # By MOI breakdown
    by_moi: dict[str, list] = {}
    for m in all_metrics:
        moi = m.moi
        by_moi.setdefault(moi, []).append(m)

    moi_metrics = {}
    for moi, metrics_list in by_moi.items():
        moi_tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        moi_fp = _false_positive_count(metrics_list)
        moi_fn = sum(1 for m in metrics_list for f in m.field_matches if f.match_type in ("missing", "none"))
        moi_p = moi_tp / (moi_tp + moi_fp) if (moi_tp + moi_fp) > 0 else 0
        moi_r = moi_tp / (moi_tp + moi_fn) if (moi_tp + moi_fn) > 0 else 0
        moi_f1 = 2 * moi_p * moi_r / (moi_p + moi_r) if (moi_p + moi_r) > 0 else 0
        std_vals = [m.standardization_accuracy for m in metrics_list if m.entity_matches]
        tc_vals = [m.track_consistency for m in metrics_list if m.track_consistency > 0]
        moi_metrics[moi] = {
            "count": len(metrics_list),
            "precision": round(moi_p, 4),
            "recall": round(moi_r, 4),
            "f1": round(moi_f1, 4),
            "standardization_accuracy": round(sum(std_vals) / len(std_vals), 4) if std_vals else 0.0,
            "track_consistency": round(sum(tc_vals) / len(tc_vals), 4) if tc_vals else 0.0,
            "over_extractions": _over_extraction_count(metrics_list),
        }

    return {
        "overall": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "over_extractions": _over_extraction_count(all_metrics),
            "entity_standardization_accuracy": round(entity_standardization_accuracy, 4),
            "cross_lingual_consistency": round(cross_lingual_consistency, 4),
        },
        "by_field": field_f1,
        "by_classification": cls_metrics,
        "by_moi": moi_metrics,
        "by_entity_type": entity_accuracy_by_type,
    }


async def run_evaluation(
    base_url: str,
    concurrency: int,
    limit: int | None = None,
    entry_ids: list[str] | None = None,
):
    """Main evaluation orchestrator."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load ground truth
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    # Only entries with source text
    entries = [e for e in entries if (GROUND_TRUTH_DIR / e["entry_id"] / "source.md").exists()]
    if entry_ids:
        id_set = set(entry_ids)
        entries = [e for e in entries if e["entry_id"] in id_set]
    if limit:
        entries = entries[:limit]
    logger.info("Evaluating {} entries", len(entries))

    # Setup
    proxy = load_proxy()
    transport_kwargs = {"proxy": proxy} if proxy else {}
    semaphore = asyncio.Semaphore(concurrency)
    engine = build_async_engine()
    sf = async_session_factory(engine)
    await preflight_database_connection(sf)

    # Load MONDO hierarchy for ontology ancestry matching
    mondo = None
    if MondoHierarchy is not None:
        try:
            mondo = MondoHierarchy.load()
            logger.info("MONDO hierarchy loaded for ontology ancestry matching")
        except (FileNotFoundError, Exception) as e:
            logger.warning("MONDO hierarchy not available: {}", e)

    t0 = time.time()
    all_metrics: list[EntryMetrics] = []

    async with httpx.AsyncClient(**transport_kwargs) as client:
        for entry in entries:
            m = await evaluate_one(client, base_url, entry, sf, semaphore, mondo=mondo)
            all_metrics.append(m)
            status_icon = "✓" if m.pipeline_status in ("awaiting_review", "completed") else "✗"
            tp = sum(1 for f in m.field_matches if f.matched)
            total = len(m.field_matches)
            entity_str = f"std={m.standardization_accuracy:.0%}" if m.entity_matches else "std=-"
            track_str = f"tc={m.track_consistency:.0%}" if m.track_consistency > 0 else "tc=-"
            logger.info("[{}] {} | {} | {}/{} fields | {} {} | {:.0f}s",
                        m.entry_id, status_icon, m.pipeline_status, tp, total,
                        entity_str, track_str, m.duration_s)

    elapsed = time.time() - t0

    # Compute aggregates
    aggregates = compute_aggregate_metrics(all_metrics)

    # Build report
    report = {
        "evaluation_id": f"eval_clingen_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {"base_url": base_url, "concurrency": concurrency, "limit": limit},
        "total_entries": len(entries),
        "total_duration_s": round(elapsed, 2),
        "aggregates": aggregates,
        "per_entry": [
            {
                "entry_id": m.entry_id,
                "gene_symbol": m.gene_symbol,
                "classification": m.classification,
                "moi": m.moi,
                "run_id": m.run_id,
                "status_url": m.status_url,
                "pipeline_status": m.pipeline_status,
                "error_message": m.error_message,
                "last_pipeline_status": m.last_pipeline_status,
                "last_current_phase": m.last_current_phase,
                "duration_s": m.duration_s,
                "evidence_count": m.evidence_count,
                "found_rate": m.found_rate,
                "grounding_rate": m.grounding_rate,
                "standardization_accuracy": m.standardization_accuracy,
                "track_consistency": m.track_consistency,
                "field_matches": [
                    {"field_id": f.field_id, "expected": f.expected_value,
                     "matched": f.matched, "extracted": f.extracted_value,
                     "source_span": f.source_span,
                     "match_type": f.match_type,
                     "extra_found_values": f.extra_found_values,
                     "best_score": f.best_score,
                     "source_score": f.source_score,
                     "confidence_score": f.confidence_score,
                     "agreement_score": f.agreement_score,
                     "status_score": f.status_score,
                     "verifier_support_score": f.verifier_support_score,
                     "target_specificity_score": f.target_specificity_score,
                     "contradiction_penalty": f.contradiction_penalty,
                     "accepted_track": f.accepted_track,
                     "normalized_value": f.normalized_value}
                    for f in m.field_matches
                ],
                "entity_matches": m.entity_matches,
            }
            for m in all_metrics
        ],
    }

    # Save report
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"eval_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    o = aggregates["overall"]
    logger.info("=== Layer 3 Evaluation Complete ===")
    logger.info("  Entries: {} | Duration: {:.0f}s", len(entries), elapsed)
    logger.info("  Field P/R/F1: {:.1%} / {:.1%} / {:.1%}", o["precision"], o["recall"], o["f1"])
    logger.info("  TP={} FP={} FN={}", o["true_positives"], o["false_positives"], o["false_negatives"])
    logger.info("  Entity Standardization Accuracy: {:.1%}", o["entity_standardization_accuracy"])
    logger.info("  Cross-lingual Consistency: {:.1%}", o["cross_lingual_consistency"])
    for cls, m in aggregates["by_classification"].items():
        logger.info("  {}: P={:.1%} R={:.1%} F1={:.1%} (n={})", cls, m["precision"], m["recall"], m["f1"], m["count"])
    for moi, m in aggregates.get("by_moi", {}).items():
        logger.info("  MOI={}: F1={:.1%} StdAcc={:.1%} TrackCons={:.1%} (n={})",
                     moi, m["f1"], m["standardization_accuracy"], m["track_consistency"], m["count"])
    logger.info("Report: {}", report_path)

    await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="+", default=None, help="Specific entry IDs to evaluate")
    args = parser.parse_args()
    asyncio.run(run_evaluation(args.base_url, args.concurrency, args.limit, args.entries))
