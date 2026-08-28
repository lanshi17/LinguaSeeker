"""Tests for ACMG-oriented evidence value normalization."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
)
from src.core.evidence_extraction.domain.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _item(field_id: str, value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
    )


def test_coordinate_only_value_is_rejected_for_hgvs_g() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.variant_hgvs_g"
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_reference_sequence_does_not_accept_coordinate_only_value() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.reference_sequence", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.reference_sequence"


def test_valid_hgvs_g_is_preserved() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "NC_000006.12:g.44270253G>A")])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == "NC_000006.12:g.44270253G>A"
    assert issues == []


def test_valid_hgvs_g_indel_dup_forms_are_preserved() -> None:
    values = [
        "NC_000006.12:g.44270253del",
        "NC_000006.12:g.44270253_44270254insA",
        "NC_000006.12:g.44270253dup",
        "NC_000006.12:g.44270253_44270260inv",
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", value) for value in values])

    assert [item.value for item in items] == values
    assert issues == []


def test_lowercase_hgvs_g_is_rejected() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("A.variant_hgvs_g", "nc_000006.12:g.44270253g>a"),
        ]
    )

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_rejected_item_clears_stale_assigned_codes() -> None:
    item = _item("A.variant_hgvs_g", "chr6_44270253").model_copy(
        update={
            "assigned_acmg_codes": ["PS1"],
            "assigned_clingen_modules": ["variant_evidence"],
        }
    )

    items, _ = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].assigned_acmg_codes == []
    assert items[0].assigned_clingen_modules == []


def test_de_novo_status_is_normalized_to_enum_value() -> None:
    inputs = [
        _item("C.de_novo_status", "not de novo").model_copy(update={"group_id": "g1"}),
        _item("C.de_novo_status", False).model_copy(update={"group_id": "g2"}),
        _item("C.de_novo_status", 0).model_copy(update={"group_id": "g3"}),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["not_de_novo", "not_de_novo", "not_de_novo"]
    value_issues = [i for i in issues if i.issue_type.value == "value_normalized"]
    assert len(value_issues) == 3


def test_de_novo_status_unknown_is_completed_explicitly() -> None:
    inputs = [
        _item("C.de_novo_status", "unknown").model_copy(update={"group_id": "g1"}),
        _item("C.de_novo_status", "not reported").model_copy(update={"group_id": "g2"}),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["unknown_not_reported", "unknown_not_reported"]


def test_protein_variant_alias_is_normalized_for_deduplication() -> None:
    inputs = [
        _item("A.variant_hgvs_p", "p.Arg168Ter").model_copy(update={"group_id": "g1"}),
        _item("A.variant_hgvs_p", "R168X").model_copy(update={"group_id": "g1"}),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert len(items) == 1
    assert items[0].value == "p.R168*"
    assert any(issue.issue_type.value == "duplicate_merged" for issue in issues)


def test_consanguinity_preserves_detail_and_normalizes_status() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("B.consanguinity", "first-degree maternal cousins"),
        ]
    )

    assert items[0].value == "present:first-degree maternal cousins"


def test_consanguinity_unknown_is_not_marked_present() -> None:
    inputs = [
        _item("B.consanguinity", "unknown").model_copy(update={"group_id": "g1"}),
        _item("B.consanguinity", "N/A").model_copy(update={"group_id": "g2"}),
        _item("B.consanguinity", "not applicable").model_copy(update={"group_id": "g3"}),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["unknown", "unknown", "unknown"]


def test_obligate_carriers_numeric_and_parent_text_normalize_to_count() -> None:
    inputs = [
        _item("C.obligate_carriers", "parents").model_copy(update={"group_id": "g1"}),
        _item("C.obligate_carriers", True).model_copy(update={"group_id": "g2"}),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == [2, 2]


def test_age_of_onset_rejects_developmental_milestone_text() -> None:
    item = _item("B.age_of_onset", "started sitting with support at the age of 15 months")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "semantic_conflict"


def test_age_of_onset_does_not_reject_non_milestone_support_text() -> None:
    item = _item("B.age_of_onset", "required respiratory support from age 2")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == "required respiratory support from age 2"
    assert issues == []


def test_in_silico_functional_phrase_is_not_functional_evidence() -> None:
    item = _item("F.functional_result", "functional analysis predicted by in silico tools")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "semantic_conflict"


def test_generic_prediction_tool_name_is_rejected() -> None:
    item = _item("E.prediction_tools_list", "in silico tools")

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "generic_prediction_tool"


def test_empty_prediction_tools_list_is_not_generic_tool_evidence() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("E.prediction_tools_list", []),
        ]
    )

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues == []


def test_mixed_prediction_tools_filters_generic_entry_with_audit_issue() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("E.prediction_tools_list", ["CADD", "in silico tools"]),
        ]
    )

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == ["CADD"]
    assert [issue.issue_type.value for issue in issues] == [
        "value_normalized",
        "generic_prediction_tool",
    ]


def test_string_prediction_tools_splits_and_filters_generic_phrases() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("E.prediction_tools_list", "CADD, in silico tools"),
        ]
    )

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == ["CADD"]
    assert [issue.issue_type.value for issue in issues] == [
        "value_normalized",
        "generic_prediction_tool",
    ]


def test_string_prediction_tools_all_generic_is_rejected() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("E.prediction_tools_list", "in silico tools, bioinformatics tools"),
        ]
    )

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "generic_prediction_tool"


def test_duplicate_facts_merge_by_group_field_and_value() -> None:
    duplicate_items = [
        _item("A.gene_symbol", "AARS2").model_copy(
            update={"group_id": "gene=AARS2|variant=__missing__", "confidence": 0.80}
        ),
        _item("A.gene_symbol", " AARS2 ").model_copy(
            update={"group_id": "gene=AARS2|variant=__missing__", "confidence": 0.95}
        ),
        _item("B.age_current_or_last_followup", "10 years").model_copy(
            update={"group_id": "gene=AARS2|variant=__missing__"}
        ),
        _item("B.age_current_or_last_followup", "10 years").model_copy(
            update={"group_id": "gene=AARS2|variant=__missing__"}
        ),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(duplicate_items)

    assert len(items) == 2
    assert items[0].field_id == "A.gene_symbol"
    assert items[0].confidence == 0.95
    assert items[0].value == "AARS2"
    assert items[1].field_id == "B.age_current_or_last_followup"
    assert items[1].value == "10 years"
    assert [issue.issue_type.value for issue in issues].count("duplicate_merged") == 2


def test_duplicate_merge_preserves_available_raw_source() -> None:
    source = SourceLocation(
        context_type="text",
        context_ref="case paragraph",
        text_snippet="AARS2",
        block_index=4,
    )
    duplicate_items = [
        _item("A.gene_symbol", "AARS2").model_copy(
            update={
                "group_id": "gene=AARS2|variant=__missing__",
                "confidence": 0.80,
                "raw_source": source,
            }
        ),
        _item("A.gene_symbol", "AARS2").model_copy(
            update={
                "group_id": "gene=AARS2|variant=__missing__",
                "confidence": 0.95,
                "raw_source": None,
            }
        ),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(duplicate_items)

    assert items[0].confidence == 0.95
    assert items[0].raw_source == source


def test_duplicate_merge_keeps_distinct_source_blocks() -> None:
    source_1 = SourceLocation(context_type="text", context_ref="case", text_snippet="AARS2", block_index=1)
    source_2 = SourceLocation(context_type="table", context_ref="Table 1", text_snippet="AARS2", block_index=7)

    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("A.gene_symbol", "AARS2").model_copy(update={"raw_source": source_1}),
            _item("A.gene_symbol", "AARS2").model_copy(update={"raw_source": source_2}),
        ]
    )

    assert len(items) == 2
    assert issues == []


def test_normalized_value_key_preserves_falsey_values() -> None:
    normalizer = AcmgEvidenceValueNormalizer()

    assert normalizer._normalized_value_key(0) != normalizer._normalized_value_key(None)
    assert normalizer._normalized_value_key(False) != normalizer._normalized_value_key(None)


def test_found_item_strips_runtime_acmg_codes() -> None:
    item = _item("C.de_novo_status", "de novo").model_copy(update={"assigned_acmg_codes": ["PS2", "PM6"]})

    items, _issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].assigned_acmg_codes == []
    assert "stripped_runtime_codes" in items[0].notes
    assert items[0].value == "de_novo"


def test_maternal_inheritance_is_not_de_novo() -> None:
    item = _item("C.de_novo_status", "de novo").model_copy(
        update={
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="该变异遗传自母亲",
            )
        }
    )

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].value == "not_de_novo"
    assert "inherited_not_de_novo" in items[0].notes
    assert issues[0].issue_type.value == "value_normalized"


def test_author_acmg_criterion_list_is_not_clinvar_assertion() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("J.clinvar_assertion", "PS2+PM2+PP3")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "semantic_conflict"
    assert "author_acmg_codes_not_clinvar" in items[0].notes


def test_unconfirmed_parental_negativity_notes_are_not_ps2_eligible() -> None:
    item = _item("C.de_novo_status", "de_novo").model_copy(
        update={
            "notes": (
                "Both parents tested and variant absent; qualifies as de novo (PS2-eligible).; "
                "review_track: approved: The variant is confirmed de novo. This is PS2-eligible."
            ),
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="变异为新生变异，父母未携带该变异位点",
            ),
        }
    )

    items, _issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].value == "de_novo"
    assert "PS2" not in items[0].notes
    assert "confirmed de novo" not in items[0].notes.casefold()
    assert "PM6-eligible" in items[0].notes
    assert "unconfirmed_parentage_not_ps2" in items[0].notes


def test_parentage_confirmed_de_novo_notes_keep_ps2_language() -> None:
    item = _item("C.de_novo_status", "de_novo").model_copy(
        update={
            "notes": "Maternity and paternity confirmed; PS2-eligible.",
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="The variant was de novo with maternity and paternity confirmation.",
            ),
        }
    )

    items, _issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].value == "de_novo"
    assert "PS2-eligible" in items[0].notes
    assert "unconfirmed_parentage_not_ps2" not in items[0].notes


def test_ocr_spaced_coding_hgvs_is_canonicalized() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_c", "c.710C&gt;G")])

    assert items[0].value == "c.710C>G"
    assert issues[0].issue_type.value == "value_normalized"


def test_nonsense_label_on_coding_deletion_becomes_frameshift() -> None:
    item = _item("A.variant_type", "nonsense").model_copy(
        update={
            "target_variant": "c.194delC",
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="c.194delC致病性突变，此为无义突变（p.S65X）",
            ),
        }
    )

    items, issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].value == "frameshift"
    assert issues[0].issue_type.value == "value_normalized"


def test_sibling_coding_hgvs_corrects_type_when_quote_omits_indel() -> None:
    """Live rett_084: the type item quotes 无义 only; c.194delC lives on A.variant_hgvs_c."""
    type_item = _item("A.variant_type", "nonsense").model_copy(
        update={
            "group_id": "g1",
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="此为无义突变（p.S65X）",
            ),
        }
    )
    hgvs_item = _item("A.variant_hgvs_c", "c.194delC").model_copy(update={"group_id": "g1"})

    items, issues = AcmgEvidenceValueNormalizer().normalize([type_item, hgvs_item])

    types = [item for item in items if item.field_id == "A.variant_type"]
    assert types[0].value == "frameshift"
    assert any(issue.issue_type.value == "value_normalized" for issue in issues)


def test_nonsense_type_stays_when_sibling_hgvs_is_a_substitution() -> None:
    type_item = _item("A.variant_type", "nonsense").model_copy(update={"group_id": "g1"})
    hgvs_item = _item("A.variant_hgvs_c", "c.538C>T").model_copy(update={"group_id": "g1"})

    items, _issues = AcmgEvidenceValueNormalizer().normalize([type_item, hgvs_item])

    types = [item for item in items if item.field_id == "A.variant_type"]
    assert types[0].value == "nonsense"


def test_frameshift_protein_hgvs_is_not_crushed_to_missense() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [_item("A.variant_hgvs_p", "p.Gly281AlafsTer20")]
    )

    assert items[0].value == "p.G281fs"
    assert issues[0].issue_type.value == "value_normalized"


def test_parentage_confirmed_without_identity_testing_is_not_confirmed() -> None:
    item = _item("C.parentage_confirmed", "confirmed").model_copy(
        update={
            "source": SourceLocation(
                context_type="text",
                context_ref="case",
                text_snippet="患儿父母均未检测到突变",
            ),
        }
    )

    items, _issues = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].value == "not_confirmed"


def test_assumed_de_novo_value_is_canonicalized() -> None:
    """B8 tells the model to write assumed de novo in notes; it often lands in value."""
    items, issues = AcmgEvidenceValueNormalizer().normalize(
        [
            _item("C.de_novo_status", "assumed de novo").model_copy(update={"group_id": "g1"}),
            _item("C.de_novo_status", "assumed_de_novo").model_copy(update={"group_id": "g2"}),
            _item("C.de_novo_status", "PM6-eligible").model_copy(update={"group_id": "g3"}),
        ]
    )

    assert [item.value for item in items] == ["de_novo", "de_novo", "de_novo"]
    assert all(issue.issue_type.value == "value_normalized" for issue in issues)
