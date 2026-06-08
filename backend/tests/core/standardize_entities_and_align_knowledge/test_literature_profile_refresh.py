"""Tests for literature profile refresh after standardization."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityType,
    BindingRole,
    MatchStatus,
    MatchMethod,
    StandardizationInput,
    StandardizationCandidate,
    EntityMatch,
)
from src.core.standardize_entities_and_align_knowledge.core import StandardizationService


def _make_service() -> tuple[StandardizationService, AsyncMock, AsyncMock]:
    """Build a service with mock matcher and repository."""
    matcher = AsyncMock()
    repository = AsyncMock()
    service = StandardizationService(matcher=matcher, repository=repository)
    return service, matcher, repository


@pytest.mark.asyncio
async def test_standardization_service_refreshes_literature_profile() -> None:
    """StandardizationService.run() triggers literature profile refresh after upsert."""
    service, matcher, repository = _make_service()

    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain1",
        track="original",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        match_method=MatchMethod.PRECISE,
    )
    matcher.match.return_value = match

    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="sd-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
        track_payloads={},
    )

    await service.run(input_data)

    # Verify refresh was called with the source_document_id.
    repository.refresh_literature_profile.assert_awaited_once_with("sd-1")


@pytest.mark.asyncio
async def test_standardization_service_refresh_called_after_upsert_canonical() -> None:
    """refresh_literature_profile is called after upsert_canonical_evidence."""
    service, matcher, repository = _make_service()

    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain1",
        track="original",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.UNMAPPED,
        external_id=None,
        display_name="BRCA1",
    )
    matcher.match.return_value = match

    input_data = StandardizationInput(
        document_id="doc-2",
        source_document_id="sd-2",
        processing_run_id="run-2",
        candidates=(candidate,),
        evidence_items=(),
        track_payloads={},
    )

    await service.run(input_data)

    # Verify the call order: refresh comes after upsert_canonical_evidence.
    call_order = [name for name, _, _ in repository.method_calls]
    assert call_order.index("refresh_literature_profile") > call_order.index("upsert_canonical_evidence")
