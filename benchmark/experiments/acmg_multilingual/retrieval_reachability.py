"""Retrieval-layer co-primary endpoint for the ACMG multilingual study.

The code-level arms read sources that a human already collected, so they cannot
answer whether an English-only pipeline could have *reached* those sources at
all. This module measures that separately: for every target
``variant x criterion family`` it records whether a pre-registered English-only
query plan and a pre-registered multilingual query plan retrieve at least one
source that carries an eligible evidence event.

Queries and provider routing are frozen in the target ledger so a probe is
reproducible and does not depend on a runtime query translator. Scoring is pure
and offline; the live probe has its own explicit ``main`` so no external search
happens during verification.

A match is exact identifier equality (normalized DOI, or PMID) between a recorded
hit and a gold eligible source. Both are needed because PubMed's summary record
for a Chinese-language article often carries a PMID but no DOI. Titles are
recorded for human audit but never used to claim a match.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

RetrievalArm = Literal["english_only", "multilingual"]

RETRIEVAL_ARMS: tuple[RetrievalArm, ...] = ("english_only", "multilingual")

_HASH_CHARS = frozenset("0123456789abcdef")
_DOI_RESOLVER_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalize_doi(value: str) -> str:
    """Return a lowercase bare DOI with any resolver prefix and slashes trimmed."""
    text = value.strip().casefold()
    for prefix in _DOI_RESOLVER_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip().strip("/")


class EligibleSource(BaseModel):
    """One frozen source adjudicated to carry eligible events for a target."""

    model_config = ConfigDict(frozen=True)

    source_family_id: str = Field(min_length=1)
    doi: str = Field(min_length=1)
    pmid: str = ""
    native_language: str = Field(min_length=2, max_length=16)
    eligible_event_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_eligible_source(self) -> EligibleSource:
        """Require an already-normalized DOI and a digits-only optional PMID."""
        if normalize_doi(self.doi) != self.doi:
            raise ValueError("doi must be stored normalized (lowercase, no resolver prefix)")
        if self.pmid and not self.pmid.isdigit():
            raise ValueError("pmid must contain digits only")
        return self


class PlannedQuery(BaseModel):
    """One pre-registered query string and the provider routing it uses."""

    model_config = ConfigDict(frozen=True)

    provider_language: str = Field(min_length=2, max_length=16)
    query: str = Field(min_length=1)


class RetrievalTarget(BaseModel):
    """One ``variant x criterion family`` retrieval unit and its gold sources."""

    model_config = ConfigDict(frozen=True)

    target_id: str = Field(min_length=1)
    gene_symbol: str = Field(min_length=1)
    disease_label: str = Field(min_length=1)
    variant_hgvs_c: str = Field(min_length=1)
    criterion_family: Literal["PS2_PM6"]
    eligible_sources: tuple[EligibleSource, ...]
    english_only_queries: tuple[PlannedQuery, ...]
    multilingual_queries: tuple[PlannedQuery, ...]

    @model_validator(mode="after")
    def validate_target(self) -> RetrievalTarget:
        """Require gold sources and keep the multilingual arm a strict superset."""
        if not self.eligible_sources:
            raise ValueError("a retrieval target needs at least one eligible source")
        source_ids = [source.source_family_id for source in self.eligible_sources]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("eligible_sources must not repeat a source_family_id")
        if not self.english_only_queries:
            raise ValueError("the English-only arm needs at least one planned query")
        for planned in self.english_only_queries:
            if planned.provider_language != "en":
                raise ValueError("english_only_queries must route to the English provider plan")
        multilingual = set(self.multilingual_queries)
        missing = [planned for planned in self.english_only_queries if planned not in multilingual]
        if missing:
            raise ValueError("multilingual_queries must include every English-only query")
        return self

    def queries_for_arm(self, arm: RetrievalArm) -> tuple[PlannedQuery, ...]:
        """Return the frozen query set a probe must send for one arm."""
        return self.english_only_queries if arm == "english_only" else self.multilingual_queries

    def eligible_event_total(self) -> int:
        """Return the gold event count reachable through any of this target's sources."""
        return sum(source.eligible_event_count for source in self.eligible_sources)


class RetrievalTargetLedger(BaseModel):
    """Frozen retrieval denominator, queries, and gold source mapping."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    created_on: str = Field(min_length=1)
    corpus_revision: str = Field(min_length=40, max_length=40)
    provenance: str = Field(min_length=1)
    denominator_note: str = Field(min_length=1)
    english_source_adjudication: Literal["pending", "complete"]
    pending_doi_source_family_ids: tuple[str, ...] = ()
    targets: tuple[RetrievalTarget, ...]

    @model_validator(mode="after")
    def validate_ledger(self) -> RetrievalTargetLedger:
        """Reject duplicate or unsorted targets before any probe is scored."""
        target_ids = [target.target_id for target in self.targets]
        if not target_ids:
            raise ValueError("the ledger needs at least one retrieval target")
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("target_id must be unique within the ledger")
        if tuple(sorted(target_ids)) != tuple(target_ids):
            raise ValueError("targets must be sorted by target_id")
        if tuple(sorted(set(self.pending_doi_source_family_ids))) != self.pending_doi_source_family_ids:
            raise ValueError("pending_doi_source_family_ids must be sorted and unique")
        return self

    def fingerprint(self) -> str:
        """Return a content digest of the targets, ignoring descriptive metadata."""
        payload = json.dumps(
            [target.model_dump(mode="json") for target in self.targets],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RetrievalHit(BaseModel):
    """One recorded search candidate, kept verbatim for later audit."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1)
    doi: str = ""
    pmid: str = ""
    title: str = ""
    url: str = ""
    language: str = ""

    @model_validator(mode="after")
    def validate_hit(self) -> RetrievalHit:
        """Require an already-normalized DOI and a digits-only optional PMID."""
        if self.doi and normalize_doi(self.doi) != self.doi:
            raise ValueError("doi must be stored normalized (lowercase, no resolver prefix)")
        if self.pmid and not self.pmid.isdigit():
            raise ValueError("pmid must contain digits only")
        return self


class ArmProbe(BaseModel):
    """The complete recorded result of probing one target under one arm."""

    model_config = ConfigDict(frozen=True)

    target_id: str = Field(min_length=1)
    arm: RetrievalArm
    probed_on: str = Field(min_length=1)
    queries: tuple[PlannedQuery, ...]
    providers: tuple[str, ...]
    hits: tuple[RetrievalHit, ...]

    @model_validator(mode="after")
    def validate_probe(self) -> ArmProbe:
        """Require at least one sent query so an empty probe cannot read as a miss."""
        if not self.queries:
            raise ValueError("a probe must record the queries it sent")
        return self


class RetrievalProbeLedger(BaseModel):
    """Content-addressed receipt binding probes to one frozen target ledger."""

    model_config = ConfigDict(frozen=True)

    study_id: str = Field(min_length=1)
    target_ledger_fingerprint: str = Field(min_length=64, max_length=64)
    probes: tuple[ArmProbe, ...]

    @model_validator(mode="after")
    def validate_probe_ledger(self) -> RetrievalProbeLedger:
        """Reject a malformed fingerprint or a repeated target/arm probe."""
        if any(character not in _HASH_CHARS for character in self.target_ledger_fingerprint):
            raise ValueError("target_ledger_fingerprint must be a lowercase SHA-256 digest")
        keys = [(probe.target_id, probe.arm) for probe in self.probes]
        if len(set(keys)) != len(keys):
            raise ValueError("each target/arm combination may be probed only once")
        return self


class TargetReachability(BaseModel):
    """Whether one arm reached one target, and through which gold sources."""

    model_config = ConfigDict(frozen=True)

    target_id: str
    arm: RetrievalArm
    reached: bool
    matched_source_family_ids: tuple[str, ...]
    reached_event_count: int = Field(ge=0)


class ArmReachabilityMetric(BaseModel):
    """Eligible-source retrieval recall for one arm over the frozen denominator."""

    model_config = ConfigDict(frozen=True)

    arm: RetrievalArm
    target_count: int = Field(ge=0)
    reached_target_count: int = Field(ge=0)
    target_recall: float = Field(ge=0.0, le=1.0)
    eligible_event_total: int = Field(ge=0)
    reached_event_count: int = Field(ge=0)
    event_recall: float = Field(ge=0.0, le=1.0)
    zero_reach_target_ids: tuple[str, ...]


class PairedReachabilityComparison(BaseModel):
    """Paired discordance for one contrast; inference is left to the analysis layer."""

    model_config = ConfigDict(frozen=True)

    baseline_arm: RetrievalArm
    comparison_arm: RetrievalArm
    target_count: int = Field(ge=0)
    both_reached_count: int = Field(ge=0)
    baseline_only_count: int = Field(ge=0)
    comparison_only_count: int = Field(ge=0)
    neither_reached_count: int = Field(ge=0)
    comparison_only_target_ids: tuple[str, ...]
    baseline_only_target_ids: tuple[str, ...]


class RetrievalRecallReport(BaseModel):
    """Stable retrieval-endpoint report bound to one target ledger fingerprint."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    target_ledger_fingerprint: str = Field(min_length=64, max_length=64)
    probe_count: int = Field(ge=0)
    reachability: tuple[TargetReachability, ...]
    metrics: tuple[ArmReachabilityMetric, ...]
    comparisons: tuple[PairedReachabilityComparison, ...]
    missing_probe_keys: tuple[str, ...]


def load_retrieval_target_ledger(path: Path) -> RetrievalTargetLedger:
    """Load the frozen retrieval target ledger from JSON."""
    return RetrievalTargetLedger.model_validate_json(path.read_text(encoding="utf-8"))


def load_retrieval_probe_ledger(path: Path) -> RetrievalProbeLedger:
    """Load one recorded probe ledger from JSON."""
    return RetrievalProbeLedger.model_validate_json(path.read_text(encoding="utf-8"))


def write_retrieval_probe_ledger(ledger: RetrievalProbeLedger, path: Path) -> None:
    """Persist a probe ledger as canonical JSON."""
    _write_json(ledger.model_dump(mode="json"), path)


def write_retrieval_recall_report(report: RetrievalRecallReport, path: Path) -> None:
    """Persist a deterministic receipt for the retrieval endpoint."""
    _write_json(report.model_dump(mode="json"), path)


def score_retrieval_reachability(
    ledger: RetrievalTargetLedger,
    probes: RetrievalProbeLedger,
) -> RetrievalRecallReport:
    """Score eligible-source retrieval recall for both arms over one ledger.

    Refuses to score while the English side of the denominator is unadjudicated,
    because an incomplete English gold set makes the paired contrast favour the
    multilingual arm by construction.
    """
    if ledger.english_source_adjudication != "complete":
        raise ValueError(
            "Cannot score retrieval recall: english_source_adjudication is 'pending'. "
            "Adjudicate which English sources carry an eligible event for each target first, "
            "otherwise the English-only arm is under-credited by construction."
        )
    fingerprint = ledger.fingerprint()
    if probes.target_ledger_fingerprint != fingerprint:
        raise ValueError("probe ledger is bound to a different target ledger fingerprint")
    unknown = sorted(
        {probe.target_id for probe in probes.probes}
        - {target.target_id for target in ledger.targets}
    )
    if unknown:
        raise ValueError("probe ledger cites unknown targets: " + ", ".join(unknown))

    probe_by_key = {(probe.target_id, probe.arm): probe for probe in probes.probes}
    reachability: list[TargetReachability] = []
    missing_probe_keys: list[str] = []
    for target in ledger.targets:
        for arm in RETRIEVAL_ARMS:
            probe = probe_by_key.get((target.target_id, arm))
            if probe is None:
                missing_probe_keys.append(f"{target.target_id}:{arm}")
            reachability.append(_resolve_reachability(target, arm, probe))

    metrics = tuple(
        _arm_metric(ledger, arm, reachability) for arm in RETRIEVAL_ARMS
    )
    comparisons = (
        _paired_comparison(ledger, "english_only", "multilingual", reachability),
    )
    return RetrievalRecallReport(
        study_id=ledger.study_id,
        target_ledger_fingerprint=fingerprint,
        probe_count=len(probes.probes),
        reachability=tuple(reachability),
        metrics=metrics,
        comparisons=comparisons,
        missing_probe_keys=tuple(missing_probe_keys),
    )


class ProbeSearchResult(BaseModel):
    """The providers consulted and candidates returned for one planned query."""

    model_config = ConfigDict(frozen=True)

    providers: tuple[str, ...]
    hits: tuple[RetrievalHit, ...]


class CandidateSearcher(Protocol):
    """Minimum search facade the live probe needs from the product."""

    async def __call__(self, *, planned: PlannedQuery, candidate_limit: int) -> ProbeSearchResult:
        """Run one pre-registered query through its language provider plan."""


async def probe_retrieval_arms(
    ledger: RetrievalTargetLedger,
    *,
    probed_on: str,
    searcher: CandidateSearcher,
    candidate_limit: int = 15,
) -> RetrievalProbeLedger:
    """Send every frozen query for every target and arm, and record the results."""
    probes: list[ArmProbe] = []
    for target in ledger.targets:
        for arm in RETRIEVAL_ARMS:
            queries = target.queries_for_arm(arm)
            providers: list[str] = []
            hits: list[RetrievalHit] = []
            for planned in queries:
                result = await searcher(planned=planned, candidate_limit=candidate_limit)
                providers.extend(result.providers)
                hits.extend(result.hits)
            probes.append(
                ArmProbe(
                    target_id=target.target_id,
                    arm=arm,
                    probed_on=probed_on,
                    queries=queries,
                    providers=tuple(sorted(set(providers))),
                    hits=_dedupe_hits(hits),
                )
            )
    return RetrievalProbeLedger(
        study_id=ledger.study_id,
        target_ledger_fingerprint=ledger.fingerprint(),
        probes=tuple(probes),
    )


def _resolve_reachability(
    target: RetrievalTarget,
    arm: RetrievalArm,
    probe: ArmProbe | None,
) -> TargetReachability:
    """Match recorded hit identifiers against this target's gold eligible sources."""
    hits = probe.hits if probe is not None else ()
    hit_dois = {hit.doi for hit in hits if hit.doi}
    hit_pmids = {hit.pmid for hit in hits if hit.pmid}
    reached_sources = tuple(
        source
        for source in target.eligible_sources
        if source.doi in hit_dois or (source.pmid and source.pmid in hit_pmids)
    )
    return TargetReachability(
        target_id=target.target_id,
        arm=arm,
        reached=bool(reached_sources),
        matched_source_family_ids=tuple(source.source_family_id for source in reached_sources),
        reached_event_count=sum(source.eligible_event_count for source in reached_sources),
    )


def _arm_metric(
    ledger: RetrievalTargetLedger,
    arm: RetrievalArm,
    reachability: Sequence[TargetReachability],
) -> ArmReachabilityMetric:
    """Summarize one arm's target-level and event-level retrieval recall."""
    arm_results = [result for result in reachability if result.arm == arm]
    target_count = len(arm_results)
    reached_target_count = sum(1 for result in arm_results if result.reached)
    eligible_event_total = sum(target.eligible_event_total() for target in ledger.targets)
    reached_event_count = sum(result.reached_event_count for result in arm_results)
    return ArmReachabilityMetric(
        arm=arm,
        target_count=target_count,
        reached_target_count=reached_target_count,
        target_recall=_ratio(reached_target_count, target_count),
        eligible_event_total=eligible_event_total,
        reached_event_count=reached_event_count,
        event_recall=_ratio(reached_event_count, eligible_event_total),
        zero_reach_target_ids=tuple(
            result.target_id for result in arm_results if not result.reached
        ),
    )


def _paired_comparison(
    ledger: RetrievalTargetLedger,
    baseline_arm: RetrievalArm,
    comparison_arm: RetrievalArm,
    reachability: Sequence[TargetReachability],
) -> PairedReachabilityComparison:
    """Return the paired discordance counts that feed an exact McNemar test."""
    reached_by_key = {(result.target_id, result.arm): result.reached for result in reachability}
    both = 0
    baseline_only: list[str] = []
    comparison_only: list[str] = []
    neither = 0
    for target in ledger.targets:
        baseline_reached = reached_by_key.get((target.target_id, baseline_arm), False)
        comparison_reached = reached_by_key.get((target.target_id, comparison_arm), False)
        if baseline_reached and comparison_reached:
            both += 1
        elif baseline_reached:
            baseline_only.append(target.target_id)
        elif comparison_reached:
            comparison_only.append(target.target_id)
        else:
            neither += 1
    return PairedReachabilityComparison(
        baseline_arm=baseline_arm,
        comparison_arm=comparison_arm,
        target_count=len(ledger.targets),
        both_reached_count=both,
        baseline_only_count=len(baseline_only),
        comparison_only_count=len(comparison_only),
        neither_reached_count=neither,
        comparison_only_target_ids=tuple(comparison_only),
        baseline_only_target_ids=tuple(baseline_only),
    )


def _dedupe_hits(hits: Sequence[RetrievalHit]) -> tuple[RetrievalHit, ...]:
    """Collapse repeated candidates while preserving first-seen order."""
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[RetrievalHit] = []
    for hit in hits:
        key = (hit.provider, hit.doi, hit.pmid, hit.url, hit.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return tuple(deduped)


def _ratio(numerator: int, denominator: int) -> float:
    """Return a bounded ratio, treating an empty denominator as zero."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _write_json(payload: object, path: Path) -> None:
    """Write canonical, sorted JSON so receipts are byte-stable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def _build_live_searcher() -> CandidateSearcher:
    """Bind the product's provider planner; keep every provider's hits.

    Reachability is identifier presence, not top-k rank. ``search_parallel``
    truncates the merged list to ``candidate_limit``, which lets Crossref
    flood out a PubMed record that has a PMID but no DOI. The probe therefore
    gathers per-provider candidates without truncating the union.
    """
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import (
        search_provider,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.normalizers import (
        normalize_items,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
        build_provider_plan,
    )

    async def search(*, planned: PlannedQuery, candidate_limit: int) -> ProbeSearchResult:
        plan = build_provider_plan(language=planned.provider_language)
        semaphore = asyncio.Semaphore(4)

        async def _search_one(item: dict[str, str]) -> list[dict[str, object]]:
            async with semaphore:
                result = await search_provider(
                    provider=item["provider"],
                    query=planned.query,
                    limit=candidate_limit,
                )
                if not result.success:
                    return []
                hits: list[dict[str, object]] = []
                for normalized in normalize_items(result.provider, result.items):
                    hits.append(
                        {
                            "provider": item["provider"],
                            "doi": normalized.doi or "",
                            "title": normalized.title or "",
                            "url": normalized.url or "",
                            "language": normalized.language or "",
                            "identifiers": dict(normalized.identifiers or {}),
                        }
                    )
                return hits

        gathered = await asyncio.gather(
            *[_search_one(item) for item in plan],
            return_exceptions=True,
        )
        collected: list[dict[str, object]] = []
        for result in gathered:
            if isinstance(result, Exception):
                continue
            collected.extend(result)
        return ProbeSearchResult(
            providers=tuple(item["provider"] for item in plan),
            hits=tuple(_hit_from_candidate(candidate) for candidate in collected),
        )

    return search


def _hit_from_candidate(candidate: dict[str, object]) -> RetrievalHit:
    """Convert one product search candidate into a typed, normalized hit."""
    raw_identifiers = candidate.get("identifiers")
    identifiers = raw_identifiers if isinstance(raw_identifiers, dict) else {}
    raw_doi = candidate.get("doi") or identifiers.get("doi") or ""
    raw_pmid = str(identifiers.get("pmid") or "").strip()
    return RetrievalHit(
        provider=str(candidate.get("provider") or "unknown"),
        doi=normalize_doi(str(raw_doi)),
        pmid=raw_pmid if raw_pmid.isdigit() else "",
        title=str(candidate.get("title") or ""),
        url=str(candidate.get("url") or ""),
        language=str(candidate.get("language") or ""),
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the explicit live retrieval-probe command line."""
    parser = argparse.ArgumentParser(description="Run the live retrieval reachability probe")
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--probed-on", required=True)
    parser.add_argument("--candidate-limit", type=int, default=15)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Contact external search providers only when this command is invoked."""
    args = _parse_args(argv)
    ledger = load_retrieval_target_ledger(args.targets)
    probes = asyncio.run(
        probe_retrieval_arms(
            ledger,
            probed_on=args.probed_on,
            searcher=_build_live_searcher(),
            candidate_limit=args.candidate_limit,
        )
    )
    write_retrieval_probe_ledger(probes, args.report)
    print(f"Recorded {len(probes.probes)} arm probes for {len(ledger.targets)} targets")


if __name__ == "__main__":
    main()
