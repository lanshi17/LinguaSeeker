"""Centralized runtime defaults for benchmark runners.

Single source of truth for operational constants that were previously
duplicated or scattered across ``benchmark/runners/*.py``. Import from here
instead of redefining::

    from benchmark.config.defaults import (
        DEFAULT_PIPELINE_BASE_URL,
        PHASE2_TERMINAL_STATUSES,
        FILTER_TIER1_KEEP_THRESHOLD,
        DEFAULT_SEED_QUERIES,
        RETT_CONFIG_PATH,
    )

Scope boundary — what lives here vs. elsewhere:

* **Here**: benchmark-run operational defaults (endpoint URL, Phase 2 status
  sets, filter thresholds, default I/O dirs, seed queries, canonical config
  file path). These are tunable parameters of benchmark execution.
* ``benchmark.core.pipeline_client``: ``POLL_INTERVAL_S`` /
  ``MAX_POLL_ATTEMPTS`` / ``TERMINAL_STATUSES`` stay there because they are
  bound to the ``submit_and_poll`` primitive and its monkeypatch contract.
* ``benchmark.core.paths``: canonical filesystem roots
  (``GROUND_TRUTH_ROOT``, ``REPORTS_ROOT``, …).

Paths are resolved from ``BENCHMARK_ROOT`` (``benchmark/core/paths.py``) so
they stay correct regardless of the runner's CWD.
"""
from __future__ import annotations

from pathlib import Path

from benchmark.core.paths import BENCHMARK_ROOT

__all__ = [
    "DEFAULT_PIPELINE_BASE_URL",
    "PHASE2_ARTIFACT_RELATIVE_PATH",
    "PHASE2_TERMINAL_STATUSES",
    "PIPELINE_FAILURE_STATUSES",
    "FILTER_TIER1_KEEP_THRESHOLD",
    "FILTER_TIER1_REJECT_THRESHOLD",
    "DEFAULT_FILTER_INPUT_DIRS",
    "DEFAULT_FILTER_OUTPUT_DIR",
    "DEFAULT_SEED_QUERIES",
    "RETT_CONFIG_PATH",
    "RETT_CONFIG_02_PATH",
]


# ── Pipeline endpoint ────────────────────────────────────────────────────────
# Default backend pipeline base URL used by the Phase 2 / benchmark-B runners.
DEFAULT_PIPELINE_BASE_URL: str = "http://localhost:8000"


# ── Phase 2 artifact + status contract ───────────────────────────────────────
# Relative location of the Phase 2 extraction result inside a processing run dir.
PHASE2_ARTIFACT_RELATIVE_PATH: Path = Path("phase_2") / "extraction_result.json"
# Phase 2 statuses that mark a run as no-longer-in-flight.
PHASE2_TERMINAL_STATUSES: set[str] = {"completed", "failed", "skipped"}
# Pipeline-level failure statuses (subset of terminal).
PIPELINE_FAILURE_STATUSES: set[str] = {"failed"}


# ── Variant-evidence filter thresholds (Tier 1 keyword scoring) ───────────────
# score >= keep  → kept; score <= reject → rejected; otherwise borderline.
FILTER_TIER1_KEEP_THRESHOLD: int = 3
FILTER_TIER1_REJECT_THRESHOLD: int = 0
# Default I/O dirs for the PDF filter runner.
DEFAULT_FILTER_INPUT_DIRS: list[Path] = [
    BENCHMARK_ROOT / "literature_acquisition" / "downloads",
    BENCHMARK_ROOT / "runners" / "downloads",
]
DEFAULT_FILTER_OUTPUT_DIR: Path = BENCHMARK_ROOT / "runners" / "downloads"


# ── Rett acquisition ─────────────────────────────────────────────────────────
# Canonical rett_config paths — the files are Ansible-deployed into
# benchmark/data/inputs/literature_acquisition/ by the rett_acquisition_config
# role. The runner's --config default points here.
RETT_CONFIG_PATH: Path = (
    BENCHMARK_ROOT / "data" / "inputs" / "literature_acquisition" / "rett_config.json"
)
RETT_CONFIG_02_PATH: Path = (
    BENCHMARK_ROOT
    / "data"
    / "inputs"
    / "literature_acquisition"
    / "rett_config_02.json"
)
# Seed queries written by ``literature_rett seed-queries``.
DEFAULT_SEED_QUERIES: list[str] = [
    "Rett syndrome MECP2 mutation case report",
    "Rett syndrome gene sequencing",
    "Rett syndrome functional study MECP2",
    "Rett syndrome CDKL5 mutation",
    "Rett syndrome FOXG1 clinical case",
    "Rett syndrome whole exome sequencing",
    "Rett syndrome genotype phenotype correlation",
    "Rett syndrome novel mutation",
    "Rett syndrome atypical case report",
    "Rett syndrome male case report",
    "Rett syndrome neurodevelopmental",
    "Rett syndrome EEG clinical",
    "Rett syndrome呼吸异常",
    "Rett综合征 基因突变",
    "Rett syndrome遺伝子変異",
    "Rett síndrome mutación genética",
    "Rett syndrome targeted sequencing",
    "Rett syndrome CRISPR model",
    "Rett syndrome mouse model functional",
    "Rett syndrome protein expression",
    "MECP2 duplication syndrome case report",
    "Rett syndrome brain derived neurotrophic factor",
    "Rett syndrome methyl CpG binding protein 2",
    "Rett syndrome临床特征",
    "Rett syndrome natural history study",
]
