"""Disease-agnostic re-annotation for unified gold-standard entries.

Extends the rett annotation toolchain (``benchmark/datasets/rett_annotation``)
to any unified entry by reusing its catalog-driven prompt, LLM client, and
evidence/variant builders -- but overriding the Rett-specific defaults
(``MECP2`` / ``HGNC:6992`` / ``Rett syndrome`` / ``XD``) with the target
gene/disease metadata read from the entry's existing ``expected.json``.

Use case: the unified-dataset audit found article-grounded entries whose
variant annotations are wrong (e.g. parkinson ``gs_085`` stored allele
frequencies as ``variant_hgvs_p``; ``gs_093`` mixed gene names into HGVS
protein strings). This tool re-annotates the specified entries with a strong
LLM (``claude-opus-4-8``) and merges the corrected ``expected_evidence`` and
``variants`` back into the unified ``expected.json``, preserving all the
schema-unified metadata fields (identifiers, source, standardization, etc.).

It only re-extracts article-grounded evidence + variants; it never touches
gene/disease/MONDO/HGNC identifiers or DB-grounded gold labels.

Usage::

    cd benchmark/datasets/rett_annotation  # .env + venv live here
    uv run python -m benchmark.analysis.dataset_curation.reannotate_unified \
        --model claude-opus-4-8 --entries gs_085 gs_093 --write

Run from the backend project to use the main venv instead::

    PYTHONPATH=.:backend uv run --project backend python -m \
        benchmark.analysis.dataset_curation.reannotate_unified \
        --model claude-opus-4-8 --entries gs_085 gs_093 --write
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Reuse the rett toolchain's disease-agnostic pieces. They live in a sibling
# package; import lazily so this module can be imported without the rett venv.
from benchmark.core.paths import BENCHMARK_ROOT

__all__ = ["reannotate_entries", "main"]

UNIFIED_ROOT = BENCHMARK_ROOT / "data" / "ground_truth" / "unified"
RETT_TOOLCHAIN_ROOT = BENCHMARK_ROOT / "datasets" / "rett_annotation"


def _import_rett_toolchain() -> dict[str, Any]:
    """Import the rett annotation toolchain's ``src`` package under a unique
    alias so it does not collide with the backend's top-level ``src`` package.

    The toolchain uses intra-package relative imports (``from .models import
    ...``), so the package must be registered in ``sys.modules`` before its
    submodules are imported.
    """
    import importlib.util

    pkg_name = "rett_annotation_toolchain"
    if pkg_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg_name,
            RETT_TOOLCHAIN_ROOT / "src" / "__init__.py",
            submodule_search_locations=[str(RETT_TOOLCHAIN_ROOT / "src")],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load rett annotation toolchain package")
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[pkg_name] = pkg
        spec.loader.exec_module(pkg)
    pkg = sys.modules[pkg_name]
    return {
        "config": importlib.import_module(f"{pkg_name}.config"),
        "catalog_annotation": importlib.import_module(f"{pkg_name}.catalog_annotation"),
        "annotator": importlib.import_module(f"{pkg_name}.annotator"),
    }


@dataclass
class ReannotationResult:
    """Outcome of re-annotating one unified entry."""

    unified_id: str
    original_entry_id: str
    status: str  # reannotated | unchanged | failed
    evidence_fields: int = 0
    variants: int = 0
    error: str = ""
    changes: dict[str, Any] = field(default_factory=dict)


def _load_unified_entry(unified_id: str) -> dict[str, Any] | None:
    path = UNIFIED_ROOT / unified_id / "expected.json"
    if not path.exists():
        logger.error("unified entry not found: {}", unified_id)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _source_expected_path(unified: dict[str, Any]) -> Path | None:
    """Locate the source-dataset ``expected.json`` for a unified entry.

    Re-annotation fixes must land in the *source* dataset so that the next
    ``build_unified_dataset`` run propagates them (the unified tree is a
    materialized artifact, not the source of truth).
    """
    dataset = unified.get("source_dataset")
    original_id = unified.get("original_entry_id")
    if not dataset or not original_id:
        return None
    return BENCHMARK_ROOT / "data" / "ground_truth" / dataset / original_id / "expected.json"


def _merge_reannotation(
    existing: dict[str, Any],
    new_expected: Any,
) -> dict[str, Any]:
    """Merge re-annotated evidence + variants into a source expected.json.

    Only ``expected_evidence`` and ``variants`` are replaced; all identifier /
    source / standardization / evaluation_config fields are preserved from the
    existing entry.
    """
    new_evidence = [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in getattr(new_expected, "expected_evidence", [])
    ]
    new_variants = [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in getattr(new_expected, "variants", [])
    ]
    merged = dict(existing)
    # Tag variants with their source (rett toolchain emits ArticleVariant
    # without a ``source`` field; article-grounded entries are "article").
    for var in new_variants:
        if "source" not in var:
            var["source"] = "article"
    merged["expected_evidence"] = new_evidence
    merged["variants"] = new_variants
    return merged


async def reannotate_one(
    modules: dict[str, Any],
    unified_id: str,
    model: str,
    write: bool,
) -> ReannotationResult:
    """Re-annotate a single unified entry, writing the fix to the *source* dataset."""
    config_module = modules["config"]
    annotator = modules["annotator"]
    expected = _load_unified_entry(unified_id)
    if expected is None:
        return ReannotationResult(unified_id, "", "failed", error="entry not found")
    source_expected_path = _source_expected_path(expected)
    if source_expected_path is None or not source_expected_path.exists():
        return ReannotationResult(
            unified_id,
            expected.get("original_entry_id", ""),
            "failed",
            error="source expected.json not found",
        )
    source_expected = json.loads(source_expected_path.read_text(encoding="utf-8"))

    source_md_path = UNIFIED_ROOT / unified_id / "source.md"
    if not source_md_path.exists():
        return ReannotationResult(
            unified_id,
            expected.get("original_entry_id", ""),
            "failed",
            error="source.md missing",
        )
    source_text = source_md_path.read_text(encoding="utf-8", errors="replace")
    # The rett annotator sends the full text when it cannot split by headings;
    # for 40-60KB articles that is too slow for opus-4-8. Cap the input so the
    # abstract + methods + results (where variants live) stay within budget.
    max_input_chars = 18000
    if len(source_text) > max_input_chars:
        source_text = source_text[:max_input_chars] + "\n\n[truncated]"
    language = str(expected.get("source_language") or "en")

    # Build a config with the requested model, reusing the rett .env API key.
    # Large articles (40-60KB) need a smaller chunk size and generous output
    # budget; opus-4-8 is slow on 143-field JSON extraction, so cap the call.
    config = config_module.Config()
    config.llm.model = model
    config.llm.timeout = max(config.llm.timeout, 300)
    config.llm.max_tokens = min(config.llm.max_tokens, 16384)
    config.annotation.chunk_size = min(config.annotation.chunk_size, 6000)

    logger.info("re-annotating {} with {}", unified_id, model)
    try:
        new_expected = await asyncio.wait_for(
            annotator.annotate_article(
                source_md=source_text,
                entry_id=unified_id,
                language=language,
                config=config,
            ),
            timeout=280,
        )
    except asyncio.TimeoutError:
        logger.warning("re-annotation timed out for {}", unified_id)
        return ReannotationResult(
            unified_id,
            expected.get("original_entry_id", ""),
            "failed",
            error="LLM call timed out (>280s)",
        )
    except Exception as exc:  # noqa: BLE001 - report per-entry, keep batch alive.
        logger.exception("re-annotation failed for {}", unified_id)
        return ReannotationResult(unified_id, expected.get("original_entry_id", ""), "failed", error=str(exc))

    if not getattr(new_expected, "expected_evidence", None):
        return ReannotationResult(
            unified_id,
            expected.get("original_entry_id", ""),
            "failed",
            error="empty annotation returned",
        )

    merged = _merge_reannotation(source_expected, new_expected)
    old_variants = source_expected.get("variants", [])
    changes = {
        "evidence_before": len(source_expected.get("expected_evidence", [])),
        "evidence_after": len(merged["expected_evidence"]),
        "variants_before": len(old_variants),
        "variants_after": len(merged["variants"]),
        "variant_p_before": [v.get("hgvs_p") for v in old_variants if v.get("hgvs_p")],
        "variant_p_after": [v.get("hgvs_p") for v in merged["variants"] if v.get("hgvs_p")],
    }

    if write:
        # Write the fix to the *source* dataset so build_unified_dataset
        # propagates it; the unified tree is a materialized artifact.
        source_expected_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "wrote corrected {} -> {} ({} evidence, {} variants)",
            unified_id,
            source_expected_path.name,
            len(merged["expected_evidence"]),
            len(merged["variants"]),
        )

    return ReannotationResult(
        unified_id=unified_id,
        original_entry_id=expected.get("original_entry_id", ""),
        status="reannotated",
        evidence_fields=len(merged["expected_evidence"]),
        variants=len(merged["variants"]),
        changes=changes,
    )


async def reannotate_entries(
    unified_ids: list[str],
    model: str,
    write: bool,
) -> list[ReannotationResult]:
    """Re-annotate a batch of unified entries concurrently."""
    modules = _import_rett_toolchain()
    semaphore = asyncio.Semaphore(2)

    async def _bounded(uid: str) -> ReannotationResult:
        async with semaphore:
            return await reannotate_one(modules, uid, model, write)

    return await asyncio.gather(*[_bounded(uid) for uid in unified_ids])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-annotate unified gold-standard entries with a strong LLM.",
    )
    parser.add_argument("--model", default="claude-opus-4-8", help="LLM model name")
    parser.add_argument("--entries", nargs="+", required=True, help="unified entry ids (gs_NNN)")
    parser.add_argument("--write", action="store_true", help="persist corrections (default: dry-run)")
    args = parser.parse_args(argv)

    results = asyncio.run(reannotate_entries(args.entries, args.model, args.write))
    print(f"\n=== Re-annotation ({'write' if args.write else 'dry-run'}): {len(results)} entries ===")
    for r in results:
        print(f"  {r.unified_id} ({r.original_entry_id}): {r.status}")
        if r.status == "reannotated":
            ch = r.changes
            print(f"    evidence: {ch['evidence_before']} -> {ch['evidence_after']}")
            print(f"    variants: {ch['variants_before']} -> {ch['variants_after']}")
            print(f"    variant_p before: {ch['variant_p_before']}")
            print(f"    variant_p after:  {ch['variant_p_after']}")
        elif r.status == "failed":
            print(f"    error: {r.error}")
    if not args.write:
        print("\n  (dry-run; re-run with --write to persist)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
