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


def test_recovery_adds_in_trans_and_parental_genotypes_from_target_variant_window() -> None:
    detected = "we detected the nonsense variant c.241C>T (p.Arg81*) in the DCLRE1C gene"
    padding = " background" * 80
    phasing = (
        "However, genetic analysis of the patient's parents demonstrated that patient P2 is, in fact, "
        "compound heterozygous. More specifically, the maternal allele was found to carry a large deletion "
        "encompassing exons 1-3, while the paternal allele harbored the c.241C>T (p.Arg81*) nonsense mutation."
    )
    text = f"{detected}{padding} {phasing}"
    document = TrackDocument(
        document_id="fused-014",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="DCLRE1C",
            disease_name="severe combined immunodeficiency due to DCLRE1C deficiency",
            variant_hgvs_c="c.241C>T",
            variant_hgvs_p="p.Arg81Ter",
        ),
    )
    items = [_item("A.gene_symbol", "DCLRE1C", detected, group_id="gene=DCLRE1C|variant=c.241C>T")]

    recovered = TargetSpanFieldRecovery().recover(document, items)

    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["C.in_trans_confirmation"] == "in_trans"
    assert "maternal allele" in str(values["C.maternal_genotype"]).casefold()
    assert "exons 1-3" in str(values["C.maternal_genotype"]).casefold()
    assert "paternal allele" in str(values["C.paternal_genotype"]).casefold()
    assert "c.241c>t" in str(values["C.paternal_genotype"]).casefold()
    in_trans = next(item for item in recovered if item.field_id == "C.in_trans_confirmation")
    assert in_trans.assigned_acmg_codes == []
    assert "compound heterozygous" in in_trans.source.text_snippet.casefold()
    assert "B.mode_of_inheritance_reported" not in values


def test_recovery_does_not_take_compound_het_from_a_different_gene() -> None:
    text = (
        "This ADA variant has been observed in compound heterozygous patients with ADA-related SCID. "
        + ("padding " * 80)
        + "Separately, we detected DCLRE1C c.241C>T (p.Arg81*) without parental studies."
    )
    document = TrackDocument(
        document_id="anti-ada",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="DCLRE1C",
            disease_name="severe combined immunodeficiency due to DCLRE1C deficiency",
            variant_hgvs_c="c.241C>T",
            variant_hgvs_p="p.Arg81Ter",
        ),
    )
    items = [_item("A.gene_symbol", "DCLRE1C", "we detected DCLRE1C c.241C>T (p.Arg81*) without parental studies")]

    recovered = TargetSpanFieldRecovery().recover(document, items)

    found_ids = {item.field_id for item in recovered if item.status == EvidenceStatus.FOUND}
    assert "C.in_trans_confirmation" not in found_ids
    assert "C.maternal_genotype" not in found_ids


def test_variant_windows_do_not_copy_nearby_gene_inheritance() -> None:
    text = (
        "Patient 2 harbored the nonsense mutation c.241C>T in DCLRE1C; "
        "patient 3 carried a hemizygous IL2RG variant associated with X-linked SCID."
    )
    document = TrackDocument(
        document_id="anti-xl",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="DCLRE1C",
            disease_name="severe combined immunodeficiency due to DCLRE1C deficiency",
            variant_hgvs_c="c.241C>T",
        ),
    )
    items = [_item("A.gene_symbol", "DCLRE1C", "Patient 2 harbored the nonsense mutation c.241C>T in DCLRE1C")]

    recovered = TargetSpanFieldRecovery().recover(document, items)

    found_ids = {item.field_id for item in recovered if item.status == EvidenceStatus.FOUND}
    assert "B.mode_of_inheritance_reported" not in found_ids


def test_recovery_splits_joint_parental_negative_into_pm6_fields() -> None:
    """A shared 父母均未检测到 quote fills both parental genotypes and assumed de novo."""
    text = (
        "对患儿及其父母进行了全外显子检测。病例存在 MECP2 基因突变 c.509C>T（p.Thr170Met）。"
        "患儿父母均未检测到突变。病例诊断为经典型 RTT。"
    )
    document = TrackDocument(
        document_id="rett-007",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name="Rett syndrome",
            variant_hgvs_c="c.509C>T",
            variant_hgvs_p="p.Thr170Met",
        ),
    )
    items = [_item("A.gene_symbol", "MECP2", text, group_id="gene=MECP2|variant=c.509C>T")]

    recovered = TargetSpanFieldRecovery().recover(document, items)
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}

    assert values["C.de_novo_status"] == "de_novo"
    assert values["C.maternal_genotype"] == "target_absent"
    assert values["C.paternal_genotype"] == "target_absent"
    assert values["C.parentage_confirmed"] == "not_confirmed"


def test_recovery_keeps_missense_only_in_child_when_synonymous_is_paternal() -> None:
    """A benign paternal synonymous change must not block missense-only-in-child de novo."""
    text = (
        "患者携带一个同义突变c.426C>T（p.F142F），同时携带一个错义突变c.468C>G（p.D156E）。"
        "同义突变c.426C>T遗传自患儿的父亲。错义突变c.468C>G只在患儿中发现，说明此突变为自发突变。"
    )
    document = TrackDocument(
        document_id="rett-085",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name="Rett syndrome",
            variant_hgvs_c="c.468C>G",
            variant_hgvs_p="p.D156E",
        ),
    )
    items = [_item("A.gene_symbol", "MECP2", "c.468C>G", group_id="gene=MECP2|variant=c.468C>G")]

    recovered = TargetSpanFieldRecovery().recover(document, items)
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}

    assert values["C.de_novo_status"] == "de_novo"
    assert values["C.maternal_genotype"] == "target_absent"
    assert values["C.paternal_genotype"] == "target_absent"
    assert values["C.parentage_confirmed"] == "not_confirmed"


def test_recovery_does_not_treat_paper_nonsense_label_as_type_for_coding_deletion() -> None:
    """c.194delC remains a coding indel even when the paper writes 无义突变 / p.S65X."""
    text = (
        "患儿MECP2基因存在c.194delC致病性突变，此为无义突变（p.S65X），"
        "即核苷酸序列中194位碱基C缺失；患儿父母在该位点均无异常。"
    )
    document = TrackDocument(
        document_id="rett-084",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name="Rett syndrome",
            variant_hgvs_c="c.194delC",
            variant_hgvs_p="p.S65X",
        ),
    )
    items = [_item("A.gene_symbol", "MECP2", text, group_id="gene=MECP2|variant=c.194delC")]

    recovered = TargetSpanFieldRecovery().recover(document, items)
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_type"] == "frameshift"
    assert values["C.maternal_genotype"] == "target_absent"
    assert values["C.parentage_confirmed"] == "not_confirmed"


def test_recovery_overwrites_llm_nonsense_when_target_is_coding_deletion() -> None:
    """LLM FOUND nonsense must not block PVS1 on c.194delC."""
    text = "患儿MECP2基因存在c.194delC致病性突变，此为无义突变（p.S65X）。"
    document = TrackDocument(
        document_id="rett-084",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name="Rett syndrome",
            variant_hgvs_c="c.194delC",
            variant_hgvs_p="p.S65X",
        ),
    )
    items = [
        _item("A.gene_symbol", "MECP2", text, group_id="gene=MECP2|variant=c.194delC"),
        _item("A.variant_type", "nonsense", "此为无义突变（p.S65X）", group_id="gene=MECP2|variant=c.194delC"),
    ]

    recovered = TargetSpanFieldRecovery().recover(document, items)
    types = [item.value for item in recovered if item.field_id == "A.variant_type"]
    assert types == ["frameshift"]
    assert "coding_indel_not_nonsense" in next(
        item.notes for item in recovered if item.field_id == "A.variant_type"
    )


def test_recovery_prefers_child_only_missense_over_paternal_synonymous_carrier() -> None:
    """A nearby 父亲...携带 about a different variant must not fill paternal genotype."""
    text = (
        "患者携带一个同义突变c.426C>T（p.F142F），同时携带一个错义突变c.468C>G（p.D156E）。"
        "同义突变c.426C>T遗传自患儿的父亲，且患儿的姐姐也同时携带，但患儿的父亲及姐姐表型均正常。"
        "错义突变c.468C>G只在患儿中发现，说明此突变为自发突变。"
    )
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.468C>G", variant_p="p.D156E"),
        [],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["C.de_novo_status"] == "de_novo"
    assert values["C.maternal_genotype"] == "target_absent"
    assert values["C.paternal_genotype"] == "target_absent"


def test_recovery_does_not_call_maternal_inheritance_de_novo() -> None:
    text = "该 MECP2 c.509C>T 变异遗传自母亲，父亲未携带该位点。"
    document = TrackDocument(
        document_id="rett-081",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name="Rett syndrome",
            variant_hgvs_c="c.509C>T",
        ),
    )
    items = [_item("A.gene_symbol", "MECP2", text, group_id="gene=MECP2|variant=c.509C>T")]

    recovered = TargetSpanFieldRecovery().recover(document, items)
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert "C.de_novo_status" not in values
    assert "C.parentage_confirmed" not in values


def _mecp2_doc(
    text: str,
    *,
    variant_c: str = "",
    variant_p: str = "",
    disease: str = "Rett syndrome",
) -> TrackDocument:
    return TrackDocument(
        document_id="mecp2-identity",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="MECP2",
            disease_name=disease,
            variant_hgvs_c=variant_c,
            variant_hgvs_p=variant_p,
        ),
    )


def test_recovery_reads_korean_table_coding_without_c_prefix() -> None:
    text = "<td>468 C→G</td><td>D 156 E</td>"
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="468 C→G", variant_p="D 156 E"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=468C>G")],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_c"] == "c.468C>G"
    assert values["A.functional_domain_or_hotspot"] == "MBD (VCEP 90-162)"


def test_recovery_does_not_invent_coding_hgvs_from_protein_only_table() -> None:
    text = "Table 2 lists D156E without a nucleotide change. Rett syndrome (RTT) is X-linked."
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="D156E", variant_p="D156E"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=D156E")],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert "A.variant_hgvs_c" not in values
    assert values["A.functional_domain_or_hotspot"] == "MBD (VCEP 90-162)"
    assert values["B.disease_diagnosis"] == "Rett syndrome"


def test_recovery_keeps_protein_string_in_coding_slot_when_paper_has_no_c_dot() -> None:
    text = "MECP2 geni 4. ekzonunda p.Pro302Leu mutasyonu heterozigot olarak saptandı."
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="p.Pro302Leu", variant_p="p.Pro302Leu"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=p.Pro302Leu")],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_c"] == "p.Pro302Leu"
    assert values["A.functional_domain_or_hotspot"] == "TRD (VCEP 302-306)"


def test_recovery_reads_xq28_dup_and_mds_only_for_dup_target() -> None:
    text = (
        "探讨 5 例 Rett 综合征（RTT）样表型。"
        "4 例患儿诊断为 RTT，1 例患儿诊断为 MECP2 重复综合征（MDS）。"
        "病例 5 发现 Xq28区域存在重复变异，片段大小为 0.299 MB。"
    )
    dup = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="Xq28_0.299Mb_dup"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=Xq28")],
    )
    dup_values = {item.field_id: item.value for item in dup if item.status == EvidenceStatus.FOUND}
    assert dup_values["A.variant_hgvs_c"] == "Xq28 0.299 Mb dup"
    assert dup_values["B.disease_diagnosis"] == "MECP2 duplication syndrome"

    point = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.509C>T", variant_p="p.Thr170Met"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=c.509C>T")],
    )
    point_values = {item.field_id: item.value for item in point if item.status == EvidenceStatus.FOUND}
    assert point_values["B.disease_diagnosis"] == "Rett syndrome"
    assert point_values.get("A.variant_hgvs_c") != "Xq28 0.299 Mb dup"


def test_recovery_completes_truncated_arg255_and_infers_nonsense() -> None:
    text = "teste genético positivo para a mutação no gene MECP2 (variante c.763C>T levando a alteração no aminoácido p. Arg255)"
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.763C>T", variant_p="p.Arg255"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=c.763C>T")],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_p"] == "p.Arg255"
    assert values["A.variant_type"] == "nonsense"


def test_recovery_fills_identity_fields_without_prior_spans() -> None:
    text = "病例 5 诊断为 MECP2 重复综合征。Xq28区域存在重复变异，片段大小为 0.299 MB。"
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="Xq28_0.299Mb_dup"),
        [],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_c"] == "Xq28 0.299 Mb dup"
    assert values["B.disease_diagnosis"] == "MECP2 duplication syndrome"


def test_recovery_reads_coding_indel_written_as_hgvs() -> None:
    text = "患儿MECP2基因存在c.194delC致病性突变，此为无义突变（p.S65X）。"
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.194delC", variant_p="p.S65X"),
        [],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_c"] == "c.194delC"
    assert values["A.variant_type"] == "frameshift"


def test_recovery_reads_french_rett_and_escaped_frameshift_star() -> None:
    text = (
        "trois patientes atteintes du syndrome de Rett. "
        "variante patogénica c.806del (p.Gly269Alafs\\*20) en MECP2"
    )
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.806del", variant_p="p.Gly269AlafsTer20"),
        [],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["B.disease_diagnosis"] == "Rett syndrome"
    assert values["A.variant_hgvs_c"] == "c.806del"
    assert values["A.variant_hgvs_p"] == "p.Gly269fs"


def test_recovery_reads_ocr_coding_without_gt() -> None:
    text = "基因编码区找到 1 个突变位点 ， c．622C Tp．Q208X（无义突变）。# Rett综合征1例"
    recovered = TargetSpanFieldRecovery().recover(
        _mecp2_doc(text, variant_c="c.622C>T", variant_p="p.Q208X"),
        [_item("A.gene_symbol", "MECP2", "MECP2", group_id="gene=MECP2|variant=c.622C>T")],
    )
    values = {item.field_id: item.value for item in recovered if item.status == EvidenceStatus.FOUND}
    assert values["A.variant_hgvs_c"] == "c.622C>T"
    assert values["B.disease_diagnosis"] == "Rett syndrome"
