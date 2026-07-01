"""Pipeline HTTP client + DB-backed metric helpers.

Carved out of ``benchmark.layer3.evaluate`` during the 2026-06-18
framework refactor. Behavior is byte-identical with the original.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import yaml
from loguru import logger
from sqlalchemy import select, text

from benchmark.core.contracts import EntryMetrics, FieldMatch
from benchmark.core.evidence_metrics import query_evidence_metrics
from benchmark.core.matching import (
    article_supported_expected_evidence,
    compare_evidence,
    fuzzy_match_value,
    mark_expected_fields_missing,
    prepare_extracted_items,
)
from benchmark.core.paths import GROUND_TRUTH_ROOT, GROUND_TRUTH_UNIFIED_ROOT, REPORTS_ROOT

try:
    from benchmark.core.mondo_hierarchy import MondoHierarchy
except ImportError:  # pragma: no cover - exercised when ontology cache absent
    MondoHierarchy = None  # type: ignore[assignment,misc]

from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.models import EvidenceEntityBinding, NormalizedEntity, RunEvidenceItem


__all__ = [
    "POLL_INTERVAL_S",
    "MAX_POLL_ATTEMPTS",
    "QUEUED_STATUSES",
    "TERMINAL_STATUSES",
    "preflight_database_connection",
    "submit_and_poll",
    "load_proxy",
    "evaluate_one",
    "compare_entity_standardization",
    "compare_track_consistency",
    "run_evaluation",
]


POLL_INTERVAL_S = 5.0
MAX_POLL_ATTEMPTS = 360  # 30 min max per entry
TERMINAL_STATUSES = {"completed", "failed"}
QUEUED_STATUSES = {"queued"}  # normal waiting state, not an error


def _compare_article_supported_evidence(
    entry: dict[str, Any],
    extracted_items: list[dict],
    *,
    mondo: Any | None = None,
) -> list[FieldMatch]:
    """Compare only expected fields valid for article-constrained recall."""
    return compare_evidence(
        article_supported_expected_evidence(entry),
        extracted_items,
        mondo=mondo,
        expected_standardization=entry.get("expected_standardization"),
    )


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


# ── Entity / track DB queries ──────────────────────────────────────────


async def compare_entity_standardization(
    session,
    run_id: str,
    expected_standardization: dict[str, str],
) -> dict[str, dict]:
    """Compare entity standardization against expected external IDs."""
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


# ── Pipeline submission ────────────────────────────────────────────────

async def submit_and_poll(
    client: httpx.AsyncClient,
    base_url: str,
    pdf_bytes: bytes | None,
    filename: str,
    pre_parsed_markdown: str | None = None,
    extraction_target: dict | None = None,
    extraction_profile: str = "none",
    extraction_mode: str = "broad",
    ablation_disable_review: bool = False,
    ablation_disable_target_guard: bool = False,
    ablation_original_only: bool = False,
    review_reject_policy: str = "hard_veto",
    extraction_track_mode: str = "dual",
) -> dict:
    """Submit document and poll until completion.

    Uses pre_parsed_markdown when provided (bypasses MinerU Phase 1).
    Falls back to PDF submission via content_base64 otherwise.

    Reads :data:`POLL_INTERVAL_S` and :data:`MAX_POLL_ATTEMPTS` from this
    module at call time so test harnesses can monkeypatch them on either
    ``benchmark.core.pipeline_client`` or the legacy
    ``benchmark.layer3.evaluate`` shim.
    """
    module = sys.modules[__name__]
    payload: dict = {
        "source_type": "local",
        "mode": "full",
        "filename": filename,
        "extraction_profile": extraction_profile,
        "extraction_mode": extraction_mode,
        "ablation_disable_review": ablation_disable_review,
        "ablation_disable_target_guard": ablation_disable_target_guard,
        "ablation_original_only": ablation_original_only,
        "review_reject_policy": review_reject_policy,
        "extraction_track_mode": extraction_track_mode,
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
    # Rate limit retry with backoff
    for _retry in range(5):
        if resp.status_code != 429:
            break
        retry_after = int(resp.headers.get("Retry-After", "10"))
        logger.warning("Rate limited (429), waiting {}s before retry", retry_after)
        await asyncio.sleep(retry_after)
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

    # Poll. Resolve constants from the module each iteration so tests that
    # monkeypatch POLL_INTERVAL_S / MAX_POLL_ATTEMPTS to 0/1 don't sit on the
    # original 30-minute defaults.
    for _attempt in range(module.MAX_POLL_ATTEMPTS):
        await asyncio.sleep(module.POLL_INTERVAL_S)
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
            if ps in QUEUED_STATUSES and _attempt % 12 == 0:
                logger.info("Task queued (waiting for slot), poll {}/{}", _attempt + 1, module.MAX_POLL_ATTEMPTS)
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
    config_path = (
        Path(__file__).resolve().parent.parent.parent
        / "backend"
        / "config"
        / "environments"
        / "development.yaml"
    )
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


# ── Per-entry evaluation ───────────────────────────────────────────────

async def evaluate_one(
    client: httpx.AsyncClient,
    base_url: str,
    entry: dict,
    sf,
    semaphore: asyncio.Semaphore,
    ground_truth_dir: Path | None = None,
    mondo: Any | None = None,
    force_reextract: bool = False,
    extraction_profile: str = "none",
    extraction_mode: str = "broad",
    ablation_disable_review: bool = False,
    ablation_disable_target_guard: bool = False,
    ablation_original_only: bool = False,
    review_reject_policy: str = "hard_veto",
    extraction_track_mode: str = "dual",
) -> EntryMetrics:
    """Evaluate one ground truth entry.

    ``ground_truth_dir`` defaults to the live module attribute
    :data:`GROUND_TRUTH_ROOT` so monkeypatching that module-level constant
    (used by both ``benchmark.core.pipeline_client`` and the
    ``benchmark.layer3.evaluate`` shim) flows through to this entrypoint.
    """
    if ground_truth_dir is None:
        ground_truth_dir = sys.modules[__name__].GROUND_TRUTH_ROOT
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
        source_dataset=entry.get("source_dataset", ""),
        original_entry_id=entry.get("original_entry_id", ""),
    )

    # Check for source text
    source_path = ground_truth_dir / entry_id / "source.md"
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
    preprocessed_path = ground_truth_dir / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    use_preprocessed = preprocessed_path.exists() and not force_reextract

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

            cleaned_items = prepare_extracted_items(extracted_items)

            # Compare evidence
            metrics.field_matches = compare_evidence(
                entry.get("expected_evidence", []),
                cleaned_items,
                mondo=mondo,
                expected_standardization=entry.get("expected_standardization"),
            )
            metrics.article_supported_field_matches = _compare_article_supported_evidence(
                entry,
                cleaned_items,
                mondo=mondo,
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
                extraction_profile=extraction_profile,
                extraction_mode=extraction_mode,
                ablation_disable_review=ablation_disable_review,
                ablation_disable_target_guard=ablation_disable_target_guard,
                ablation_original_only=ablation_original_only,
                review_reject_policy=review_reject_policy,
                extraction_track_mode=extraction_track_mode,
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

            if metrics.pipeline_status == "completed":
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

                    cleaned_items = prepare_extracted_items(extracted_items)

                    # Compare
                    metrics.field_matches = compare_evidence(
                        entry.get("expected_evidence", []),
                        cleaned_items,
                        mondo=mondo,
                        expected_standardization=entry.get("expected_standardization"),
                    )
                    metrics.article_supported_field_matches = _compare_article_supported_evidence(
                        entry,
                        cleaned_items,
                        mondo=mondo,
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


# ── Entry loading / sharding ───────────────────────────────────────────


def _load_entries(ground_truth_root: Path) -> list[dict]:
    """Load entries from ``selection.json`` or ``manifest.json``.

    The unified dataset uses ``manifest.json`` with a different schema than
    legacy datasets that ship ``selection.json``.  This function normalizes
    both into the flat entry format expected by :func:`evaluate_one`.

    Returns:
        List of dicts with at least ``entry_id``, ``gene_symbol``,
        ``classification``, ``moi``, ``disease_label``.  Unified entries
        additionally carry ``source_dataset`` and ``original_entry_id``.
    """
    selection_path = ground_truth_root / "selection.json"
    manifest_path = ground_truth_root / "manifest.json"

    if selection_path.exists():
        return json.loads(selection_path.read_text(encoding="utf-8"))

    if manifest_path.exists():
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries: list[dict] = []
        for item in raw.get("entries", []):
            entry_dir = ground_truth_root / item["unified_id"]
            expected_path = entry_dir / "expected.json"
            if not expected_path.exists():
                continue
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            # Manifest carries gene/disease metadata; expected.json carries
            # the evaluation-specific fields (evidence, standardization, entities).
            # Merge them, preferring expected.json for evaluation fields.
            entry = {
                "entry_id": item["unified_id"],
                "gene_symbol": expected.get("gene_symbol") or item.get("gene_symbol", ""),
                "classification": expected.get("classification") or item.get("classification", ""),
                "moi": expected.get("moi") or item.get("moi", ""),
                "disease_label": expected.get("disease_label") or item.get("disease_label", ""),
                "source_dataset": item.get("source_dataset", expected.get("source_dataset", "")),
                "original_entry_id": item.get("original_entry_id", expected.get("original_entry_id", "")),
                "expected_evidence": expected.get("expected_evidence", []),
                "expected_standardization": expected.get("expected_standardization", {}),
                "expected_entities": expected.get("expected_entities", {}),
            }
            entries.append(entry)
        return entries

    raise FileNotFoundError(
        f"No selection.json or manifest.json found in {ground_truth_root}"
    )


def _apply_shard(
    entries: list[dict],
    *,
    entry_ids: list[str] | None = None,
    shard_index: int | None = None,
    shard_size: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Filter entries by explicit IDs, shard slice, or limit.

    Priority: ``entry_ids`` > ``shard_index``+``shard_size`` > ``limit``.
    """
    result = entries

    if entry_ids:
        id_set = set(entry_ids)
        result = [e for e in result if e["entry_id"] in id_set]
    elif shard_index is not None and shard_size is not None:
        start = shard_index * shard_size
        result = result[start : start + shard_size]
    elif limit:
        result = result[:limit]

    return result


def _compute_stratified_metrics(all_metrics: list[EntryMetrics]) -> dict[str, dict]:
    """Compute P/R/F1 grouped by ``source_dataset`` for unified evaluations.

    Returns a dict keyed by source_dataset name (e.g. ``clingen``,
    ``clinvar_fused``, ``rett``, ``parkinson``), each containing the same
    shape as ``compute_aggregate_metrics()["overall"]`` plus a ``count``.
    """
    from benchmark.core.aggregate import compute_aggregate_metrics

    groups: dict[str, list[EntryMetrics]] = {}
    for m in all_metrics:
        key = m.source_dataset or "unknown"
        groups.setdefault(key, []).append(m)

    result: dict[str, dict] = {}
    for key, metrics_list in sorted(groups.items()):
        agg = compute_aggregate_metrics(metrics_list)
        result[key] = {**agg["overall"], "count": len(metrics_list)}

    return result


# ── Top-level orchestrator ─────────────────────────────────────────────

async def run_evaluation(
    base_url: str,
    concurrency: int,
    limit: int | None = None,
    entry_ids: list[str] | None = None,
    ground_truth_root: Path = GROUND_TRUTH_ROOT,
    force_reextract: bool = False,
    api_key: str | None = None,
    extraction_profile: str = "none",
    extraction_mode: str = "broad",
    shard_index: int | None = None,
    shard_size: int | None = None,
    ablation_disable_review: bool = False,
    ablation_disable_target_guard: bool = False,
    ablation_original_only: bool = False,
    review_reject_policy: str = "hard_veto",
    extraction_track_mode: str = "dual",
):
    """Main evaluation orchestrator.

    Supports three entry-selection modes (in priority order):

    1. ``entry_ids`` \u2014 evaluate only the listed entry IDs.
    2. ``shard_index`` + ``shard_size`` \u2014 evaluate one deterministic shard
       (``entries[shard_index*shard_size : (shard_index+1)*shard_size]``).
    3. ``limit`` \u2014 evaluate the first N entries.

    When the ground truth root contains ``manifest.json`` (unified dataset),
    entries are loaded from the manifest automatically.  Legacy datasets that
    ship ``selection.json`` continue to work unchanged.
    """
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    # Load ground truth \u2014 supports both selection.json (legacy) and
    # manifest.json (unified) via _load_entries().
    all_entries = _load_entries(ground_truth_root)
    entries = [e for e in all_entries if (ground_truth_root / e["entry_id"] / "source.md").exists()]
    entries = _apply_shard(
        entries,
        entry_ids=entry_ids,
        shard_index=shard_index,
        shard_size=shard_size,
        limit=limit,
    )
    is_unified = ground_truth_root == GROUND_TRUTH_UNIFIED_ROOT or (ground_truth_root / "manifest.json").exists()
    ds_label = "unified" if is_unified else ground_truth_root.name
    logger.info("Evaluating {} entries from {} dataset", len(entries), ds_label)

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
    client_kwargs = dict(transport_kwargs)
    if api_key:
        client_kwargs["headers"] = {"X-API-Key": api_key}
    async with httpx.AsyncClient(**client_kwargs) as client:
        for entry in entries:
            m = await evaluate_one(
                client,
                base_url,
                entry,
                sf,
                semaphore,
                ground_truth_dir=ground_truth_root,
                mondo=mondo,
                force_reextract=force_reextract,
                extraction_profile=extraction_profile,
                extraction_mode=extraction_mode,
                ablation_disable_review=ablation_disable_review,
                ablation_disable_target_guard=ablation_disable_target_guard,
                ablation_original_only=ablation_original_only,
                review_reject_policy=review_reject_policy,
                extraction_track_mode=extraction_track_mode,
            )
            all_metrics.append(m)
            status_icon = "\u2713" if m.pipeline_status == "completed" else "\u2717"
            tp = sum(1 for f in m.field_matches if f.matched)
            total = len(m.field_matches)
            entity_str = f"std={m.standardization_accuracy:.0%}" if m.entity_matches else "std=-"
            track_str = f"tc={m.track_consistency:.0%}" if m.track_consistency > 0 else "tc=-"
            logger.info("[{}] {} | {} | {}/{} fields | {} {} | {:.0f}s",
                        m.entry_id, status_icon, m.pipeline_status, tp, total,
                        entity_str, track_str, m.duration_s)

    elapsed = time.time() - t0

    # Compute aggregates (deferred import keeps the pure-eval path free of httpx deps)
    from benchmark.core.aggregate import compute_aggregate_metrics

    aggregates = compute_aggregate_metrics(all_metrics)
    article_supported_metrics = [
        replace(m, field_matches=m.article_supported_field_matches)
        for m in all_metrics
    ]
    article_supported_aggregates = compute_aggregate_metrics(article_supported_metrics)

    # Build report \u2014 include provenance and shard metadata
    report: dict[str, Any] = {
        "evaluation_id": f"eval_{ds_label}_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "base_url": base_url,
            "concurrency": concurrency,
            "limit": limit,
            "ground_truth_root": str(ground_truth_root),
            "dataset": ds_label,
            "extraction_profile": extraction_profile,
            "extraction_mode": extraction_mode,
            "ablation_disable_review": ablation_disable_review,
            "ablation_disable_target_guard": ablation_disable_target_guard,
            "ablation_original_only": ablation_original_only,
            "review_reject_policy": review_reject_policy,
            "extraction_track_mode": extraction_track_mode,
            "shard_index": shard_index,
            "shard_size": shard_size,
            "metric_views": ["raw", "article_supported"],
        },
        "total_entries": len(entries),
        "total_duration_s": round(elapsed, 2),
        "aggregates": {
            **aggregates,
            "article_supported": article_supported_aggregates["overall"],
        },
        "per_entry": [
            {
                "entry_id": m.entry_id,
                "gene_symbol": m.gene_symbol,
                "classification": m.classification,
                "moi": m.moi,
                "source_dataset": m.source_dataset,
                "original_entry_id": m.original_entry_id,
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
                "article_supported_field_matches": [
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
                    for f in m.article_supported_field_matches
                ],
                "entity_matches": m.entity_matches,
            }
            for m in all_metrics
        ],
    }

    # Add by_source_dataset stratification when running unified
    if is_unified:
        report["aggregates"]["by_source_dataset"] = _compute_stratified_metrics(all_metrics)
        report["aggregates"]["timeout_and_errors"] = [
            {"entry_id": m.entry_id, "source_dataset": m.source_dataset, "pipeline_status": m.pipeline_status, "error_message": m.error_message}
            for m in all_metrics
            if m.pipeline_status in ("timeout", "error", "failed")
        ]

    # Save report \u2014 include shard suffix when applicable
    ts = time.strftime("%Y%m%d_%H%M%S")
    shard_suffix = f"_shard{shard_index}" if shard_index is not None else ""
    report_path = REPORTS_ROOT / f"eval_{ds_label}_{ts}{shard_suffix}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    o = aggregates["overall"]
    logger.info("=== Evaluation Complete ({}) ===", ds_label)
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
    if is_unified:
        for sds, m in report["aggregates"].get("by_source_dataset", {}).items():
            logger.info("  source={}: P={:.1%} R={:.1%} F1={:.1%} (n={})", sds, m["precision"], m["recall"], m["f1"], m["count"])
    logger.info("Report: {}", report_path)

    await engine.dispose()
