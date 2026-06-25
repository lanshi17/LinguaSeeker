from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    build_block_prompt_text,
    get_catalog_extraction_prompt,
    get_channel_strategy_guidance,
    get_evidence_map_prompt,
    relationship_decision_guidance,
)


def test_evidence_map_prompt_defaults_to_relevant_before_task():
    """DEFAULT instruction must appear before TASK so FAST models see it first."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    default_pos = prompt.index("DEFAULT")
    task_pos = prompt.index("TASK")
    assert default_pos < task_pos, "DEFAULT must appear before TASK in the prompt"


def test_evidence_map_prompt_has_uncertainty_safety_net():
    """Prompt must include an explicit 'if unsure, set TRUE' safety net."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "unsure" in prompt.lower()
    assert "true" in prompt.lower()


def test_evidence_map_prompt_lists_not_relevant_categories():
    """Prompt must enumerate the three NOT_RELEVANT categories."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    lower = prompt.lower()
    assert "methodological" in lower or "statistical methods" in lower
    assert "editorial" in lower or "letter" in lower or "comment" in lower
    assert "unrelated" in lower


def test_evidence_map_prompt_contains_document_id():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "doc-1" in prompt


def test_evidence_map_prompt_requests_json_object():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")

    assert "json" in prompt.lower()
    assert '"relevant": true' in prompt.lower()
    assert '"gene_terms"' in prompt


def test_catalog_prompt_includes_catalog_field_ids():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "A.variant_type" in prompt
    assert "status" in prompt
    assert "not_found" in prompt


def test_catalog_prompt_declares_pre_scoped_eligible_fields() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    lower = prompt.lower()
    assert "pre-scoped" in lower
    assert "eligible fields" in lower
    assert "do not add fields outside this catalog" in lower
    assert "set status=\"not_found\" for listed eligible fields" in lower


def test_catalog_prompt_absorbs_expanded_field_guidance_without_baseline_limits() -> None:
    """Pipeline prompt should absorb B7 field coverage guidance, not its baseline constraints."""
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="MECP2 de novo variant in Rett syndrome",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="MECP2; Rett syndrome; de novo",
    )

    assert "EXPANDED FIELD COVERAGE GUIDANCE" in prompt
    assert "A.variant_hgvs_c" in prompt
    assert "A.variant_hgvs_p" in prompt
    assert "A.variant_consequence_class" in prompt
    assert "B.age_of_onset" in prompt
    assert "B.mode_of_inheritance_reported" in prompt
    assert "C.inheritance_source" in prompt
    assert "C.de_novo_status" in prompt
    lower = prompt.lower()
    assert "do not use tools" not in lower
    assert "do not use" not in lower or "multi-stage pipeline" not in lower


def test_catalog_prompt_defines_ocr_gap_and_external_completion_boundaries():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "ocr_gap" in prompt
    assert "Do not invent external database values" in prompt
    assert "baseline biochemical markers" in prompt
    assert "treatment response" in prompt
    assert "diagnosis_sufficiency" in prompt


def test_catalog_prompt_requires_verbatim_source_snippets():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "snippet must be a verbatim" in prompt.lower()
    assert "copy punctuation exactly" in prompt.lower()


def test_build_block_prompt_text_uses_original_block_indices_and_captions():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="header", page_idx=0, text="Header"),
            ContentBlock(
                type="table",
                page_idx=1,
                table_caption=["Table 1. Variants"],
                table_body="BRCA1 c.5266dupC",
            ),
        ],
    )

    text = build_block_prompt_text(doc)

    assert "[Block 0 | text | page 1]" in text
    assert "[Block 1 | table | page 2 | caption: Table 1. Variants]" in text
    assert "BRCA1 c.5266dupC" in text


def test_catalog_prompt_uses_block_sources_without_offsets():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="[Block 1 | table | page 2]\nBRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "block_index" in prompt
    assert "Do not calculate character offsets" in prompt
    assert "raw source" not in prompt.lower()


def test_special_evidence_prompt_requires_verbatim_snippets():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import get_special_evidence_prompt

    prompt = get_special_evidence_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        current_items_summary="A.gene_symbol: BRCA1",
    )

    assert "reuse exact document wording" in prompt.lower()
    assert "copy punctuation exactly" in prompt.lower()


def test_build_block_prompt_text_can_select_original_block_indices():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Title"),
            ContentBlock(type="text", page_idx=1, text="BRCA1 c.5266dupC"),
            ContentBlock(type="table", page_idx=2, table_body="GLA c.1000G>A"),
        ],
    )

    text = build_block_prompt_text(doc, block_indices=(1, 2))

    assert "[Block 0" not in text
    assert "[Block 1 | text | page 2]" in text
    assert "[Block 2 | table | page 3]" in text


def test_catalog_prompt_distinguishes_age_of_onset_from_milestones() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="started sitting with support at the age of 15 months; referred at 17 months",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Do NOT use developmental milestones as B.age_of_onset" in prompt
    assert "referral, diagnosis, first symptoms, or presentation age" in prompt


def test_catalog_prompt_requires_named_prediction_tools() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="functional analysis by in silico tools",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Computational predictions support PP3/BP4 only" in prompt
    assert "Do not treat in silico predictions as F.functional_result" in prompt
    assert "E.prediction_tools_list requires named tools" in prompt


def test_catalog_prompt_requires_gene_symbol_from_disease_prefix() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS2-mutation related mitochondrial disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "A.gene_symbol" in prompt
    assert "AARS2-related" in prompt
    assert "must extract the gene symbol independently" in prompt
    assert "must not leave A.gene_symbol as not_found" in prompt


def test_catalog_prompt_relationship_distinguishes_established_from_preliminary() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS1 causes Charcot-Marie-Tooth disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS1 case",
    )

    assert "known disease gene" in prompt
    assert "established causal relationship" in prompt
    assert "Do not choose associated merely because the sentence contains associated" in prompt


def test_catalog_prompt_relationship_mentions_unclear_and_predicted_cues() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="The relationship remains unclear and some targets are predicted",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS1 case",
    )

    lower = prompt.lower()
    assert "pathogenic-link-unclear" in lower
    assert "predicted targets" in lower
    assert "may be due" in lower or "might be due" in lower


def test_relationship_decision_guidance_defines_every_allowed_relationship_label() -> None:
    guidance = relationship_decision_guidance()

    expected_definitions = {
        "causative": "established causal",
        "associated": "preliminary",
        "susceptibility": "risk",
        "uncertain": "insufficient",
        "disputed": "conflicting",
        "refuted": "evidence against",
        "no_relationship": "no gene-disease relationship",
    }
    for label, required_phrase in expected_definitions.items():
        assert f'"{label}"' in guidance
        assert required_phrase in guidance


def test_catalog_prompt_has_target_only_disease_boundary_guidance() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="The paper lists lupus, infection, and background autoimmune diseases.",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="TLR5 case",
    )

    assert "target disease boundary" in prompt.lower()
    assert "Do NOT extract disease lists" in prompt
    assert "Do NOT extract comorbidities" in prompt
    assert "Do NOT extract background diseases" in prompt
    assert "Do NOT over-specialize or under-specialize the target disease name" in prompt


def test_catalog_prompt_declares_target_and_strict_entity_rules() -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        ExtractionTarget,
    )

    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="ABCA3 and CFTR are mentioned.",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="Genes: ABCA3, CFTR",
        extraction_target=target,
    )

    assert "TARGET GENE: ABCA3" in prompt
    assert "TARGET DISEASE: interstitial lung disease due to ABCA3 deficiency" in prompt
    assert "Extract evidence ONLY for the target gene-disease pair" in prompt
    assert "Other genes mentioned for comparison" in prompt
    assert "gene_symbol field MUST be a single string" in prompt
    assert "evidence_role" in prompt
    assert '"primary"' in prompt
    assert '"phenotype"' in prompt
    assert '"comparator"' in prompt
    assert '"context"' in prompt


def test_catalog_prompt_omits_target_section_when_not_provided() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="ABCA3",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "TARGET GENE:" not in prompt
    assert "TARGET DISEASE:" not in prompt


# ---------------------------------------------------------------------------
# Channel strategy guidance tests
# ---------------------------------------------------------------------------

def _cls(channels: list[DocumentEvidenceChannel]) -> DocumentChannelClassification:
    return DocumentChannelClassification(
        selected_channels=list(channels),
        confidence=0.9,
        rationale="test",
        supporting_block_ids=[],
    )


def _catalog_prompt(channel_classification=None) -> str:
    return get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="GLA c.1000G>A Fabry disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="GLA Fabry disease",
        channel_classification=channel_classification,
    )


def test_channel_strategy_none_returns_generic():
    guidance = get_channel_strategy_guidance(None)
    assert "DOCUMENT-CHANNEL STRATEGY" in guidance
    assert "standard catalog rules" in guidance


def test_channel_strategy_unknown_returns_generic():
    guidance = get_channel_strategy_guidance(_cls([DocumentEvidenceChannel.UNKNOWN]))
    assert "DOCUMENT-CHANNEL STRATEGY" in guidance
    assert "standard catalog rules" in guidance
    assert "CASE-REPORT STRATEGY" not in guidance
    assert "FUNCTIONAL-STUDY STRATEGY" not in guidance


def test_channel_strategy_case_report_emphasizes_patient_proband_family():
    guidance = get_channel_strategy_guidance(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    assert "CASE-REPORT STRATEGY" in guidance
    assert "phenotype" in guidance.lower()
    assert "proband" in guidance.lower()
    assert "family" in guidance.lower()
    assert "segregation" in guidance.lower()
    assert "de novo" in guidance.lower()
    assert "zygosity" in guidance.lower()


def test_channel_strategy_functional_study_blocks_in_silico_as_functional():
    guidance = get_channel_strategy_guidance(_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]))
    assert "FUNCTIONAL-STUDY STRATEGY" in guidance
    assert "assay" in guidance.lower()
    assert "controls" in guidance.lower()
    assert "quantitative" in guidance.lower()
    assert "in silico" in guidance.lower()
    assert "Do not treat in silico" in guidance


def test_channel_strategy_cohort_study_emphasizes_aggregate():
    guidance = get_channel_strategy_guidance(_cls([DocumentEvidenceChannel.COHORT_STUDY]))
    assert "COHORT-STUDY STRATEGY" in guidance
    assert "cohort" in guidance.lower()
    assert "sample size" in guidance.lower() or "cohort size" in guidance.lower()
    assert "statistical" in guidance.lower()
    assert "odds ratio" in guidance.lower()
    assert "population frequency" in guidance.lower()


def test_channel_strategy_mixed_concrete_concatenates_without_duplicate_generic():
    guidance = get_channel_strategy_guidance(
        _cls([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    assert "CASE-REPORT STRATEGY" in guidance
    assert "FUNCTIONAL-STUDY STRATEGY" in guidance
    # No generic text when concrete channels are present
    assert "standard catalog rules" not in guidance

def test_channel_strategy_bare_mixed_expands_to_all_concrete():
    """Bare MIXED expands effective_channels to all three concrete channels."""
    guidance = get_channel_strategy_guidance(_cls([DocumentEvidenceChannel.MIXED]))
    assert "CASE-REPORT STRATEGY" in guidance
    assert "FUNCTIONAL-STUDY STRATEGY" in guidance
    assert "COHORT-STUDY STRATEGY" in guidance
    assert "standard catalog rules" not in guidance


def test_catalog_prompt_case_report_contains_strategy_and_not_functional_strategy():
    prompt = _catalog_prompt(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    assert "CASE-REPORT STRATEGY" in prompt
    assert "FUNCTIONAL-STUDY STRATEGY" not in prompt
    assert "COHORT-STUDY STRATEGY" not in prompt


def test_catalog_prompt_functional_study_contains_assay_strategy():
    prompt = _catalog_prompt(_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]))
    assert "FUNCTIONAL-STUDY STRATEGY" in prompt
    assert "CASE-REPORT STRATEGY" not in prompt


def test_catalog_prompt_cohort_study_contains_cohort_strategy():
    prompt = _catalog_prompt(_cls([DocumentEvidenceChannel.COHORT_STUDY]))
    assert "COHORT-STUDY STRATEGY" in prompt
    assert "FUNCTIONAL-STUDY STRATEGY" not in prompt


def test_catalog_prompt_mixed_contains_both_strategy_sections():
    prompt = _catalog_prompt(
        _cls([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    assert "CASE-REPORT STRATEGY" in prompt
    assert "FUNCTIONAL-STUDY STRATEGY" in prompt


def test_catalog_prompt_unknown_uses_generic_strategy():
    prompt = _catalog_prompt(_cls([DocumentEvidenceChannel.UNKNOWN]))
    assert "DOCUMENT-CHANNEL STRATEGY" in prompt
    assert "standard catalog rules" in prompt
    assert "CASE-REPORT STRATEGY" not in prompt


def test_catalog_prompt_none_classification_uses_generic_strategy():
    prompt = _catalog_prompt(None)
    assert "DOCUMENT-CHANNEL STRATEGY" in prompt
    assert "standard catalog rules" in prompt

def test_catalog_prompt_strategy_appears_between_catalog_scope_and_rules():
    prompt = _catalog_prompt(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    scope_pos = prompt.index("CATALOG SCOPE:")
    # Use rfind for "CASE-REPORT STRATEGY" — the strategy block heading may
    # collide with catalog field text; the injected section is the last match.
    strategy_pos = prompt.rindex("CASE-REPORT STRATEGY")
    rules_pos = prompt.rindex("RULES:")
    assert scope_pos < strategy_pos < rules_pos
