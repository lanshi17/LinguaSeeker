from src.core.evidence_extraction.contracts import (
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    SourceLocation,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.postprocess.target_span_recovery import (
    TargetSpanFieldRecovery,
)


def _doc(
    text: str, *, gene: str = "ABCA4", disease: str = "Stargardt disease", variant: str = "p.Gly1961Glu"
) -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol=gene,
            disease_name=disease,
            variant_hgvs_p=variant,
        ),
    )


def _item(
    field_id: str,
    value: str | list[str],
    source_text: str,
    *,
    group_id: str = "gene=ABCA4|variant=p.Gly1961Glu",
) -> EvidenceItem:
    category, field_name = field_id.split(".", maxsplit=1)
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_name,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        group_id=group_id,
        source=SourceLocation(
            context_type="text",
            context_ref="target",
            text_snippet=source_text,
        ),
    )


def test_recovery_adds_missing_inheritance_from_target_span() -> None:
    text = "Stargardt disease results from biallelic pathogenic variants in the ABCA4 gene."
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("B.disease_diagnosis", "Stargardt disease", text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["B.mode_of_inheritance_reported"] == "AR"
    inheritance = next(item for item in recovered if item.field_id == "B.mode_of_inheritance_reported")
    assert inheritance.assigned_acmg_codes == []
    assert inheritance.assigned_clingen_modules == []


def test_recovery_adds_missing_gene_disease_relationship_from_causal_target_span() -> None:
    text = "Biallelic pathogenic variants in ABCA4 cause Stargardt disease."
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("B.disease_diagnosis", "Stargardt disease", text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.gene_disease_relationship"] == "causative"


def test_recovery_adds_missing_variant_type_from_target_variant_pattern() -> None:
    text = "The patient carries ABCA4 c.5882G>A (p.Gly1961Glu), a missense variant."
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("A.variant_hgvs_p", "p.Gly1961Glu", text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_type"] == "missense"


def test_recovery_adds_missing_clinvar_assertion_from_pathogenic_target_table_row() -> None:
    text = "ABCA4 | c.5882G>A | p.Gly1961Glu | PATHOGENIC"
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("A.variant_hgvs_p", "p.Gly1961Glu", text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["J.clinvar_assertion"] == "Pathogenic"


def test_recovery_does_not_overwrite_existing_found_field() -> None:
    text = "ABCA4 | c.5882G>A | p.Gly1961Glu | PATHOGENIC"
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("J.clinvar_assertion", "Likely pathogenic", text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    assertions = [item.value for item in recovered if item.field_id == "J.clinvar_assertion"]
    assert assertions == ["Likely pathogenic"]


def test_recovery_treats_existing_list_value_as_present() -> None:
    text = "ABCA4 | c.5882G>A | p.Gly1961Glu | PATHOGENIC"
    items = [
        _item("A.gene_symbol", "ABCA4", text),
        _item("J.clinvar_assertion", ["Pathogenic"], text),
    ]

    recovered = TargetSpanFieldRecovery().recover(_doc(text), items)

    assertions = [item.value for item in recovered if item.field_id == "J.clinvar_assertion"]
    assert assertions == [["Pathogenic"]]


def test_recovery_does_not_treat_de_novo_as_autosomal_dominant() -> None:
    text = "The MECP2 variant was de novo in the proband."
    items = [_item("A.gene_symbol", "MECP2", text, group_id="gene=MECP2|variant=c.509C>T")]

    recovered = TargetSpanFieldRecovery().recover(
        _doc(text, gene="MECP2", disease="Rett syndrome", variant="c.509C>T"),
        items,
    )

    found_ids = {item.field_id for item in recovered if item.status == EvidenceStatus.FOUND}
    assert "B.mode_of_inheritance_reported" not in found_ids
