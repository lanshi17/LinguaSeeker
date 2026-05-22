from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import SourceGrounder


def _doc() -> TrackDocument:
    text = "Page one BRCA1 evidence.\n\nPage two has c.68_69delAG evidence."
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[
            PageSpan(span_id="p1", page=1, start_offset=0, end_offset=24),
            PageSpan(span_id="p2", page=2, start_offset=26, end_offset=len(text)),
        ],
    )


def test_source_grounding_keeps_exact_source():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=9,
            end_offset=14,
            context_type="text",
            context_ref="Results",
            text_snippet="BRCA1",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.source_precision == SourcePrecision.EXACT
    assert grounded[0].raw_source is None


def test_source_grounding_corrects_wrong_offset():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS cDNA",
        status=EvidenceStatus.FOUND,
        value="c.68_69delAG",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=12,
            context_type="text",
            context_ref="Table 1",
            text_snippet="c.68_69delAG",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.page == 2
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
    assert grounded[0].raw_source is not None


def test_source_grounding_marks_snippet_not_found_as_source_invalid():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="TP53",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=4,
            context_type="text",
            context_ref="Results",
            text_snippet="TP53",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].status == EvidenceStatus.SOURCE_INVALID
    assert grounded[0].raw_source is not None
    assert grounded[0].raw_source.text_snippet == "TP53"


def test_source_grounding_marks_missing_image_source_as_ocr_gap():
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value="p.R227X",
        source=SourceLocation(
            span_id="fig-1",
            page=2,
            start_offset=0,
            end_offset=6,
            context_type="figure",
            context_ref="Figure 1",
            text_snippet="p.R227X",
            block_type="image",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
        inference_basis=["Variant appears in sequencing trace image."],
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].status == EvidenceStatus.OCR_GAP
    assert grounded[0].raw_source is not None
    assert grounded[0].inference_basis == ["Variant appears in sequencing trace image."]


def test_source_grounding_normalizes_cjk_ocr_spacing_before_marking_invalid():
    document = TrackDocument(
        document_id="doc-zh",
        track=Track.ORIGINAL,
        formatted_text="由于位于的基因变异致使半乳糖苷酶活性降低，其代谢底物在体内大量贮积。",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=36)],
    )
    item = EvidenceItem(
        field_id="A.gene_disease_relationship",
        category="A",
        field_name="Gene disease relationship",
        status=EvidenceStatus.FOUND,
        value="GLA基因变异导致法布雷病",
        source=SourceLocation(
            span_id="raw-1",
            page=1,
            start_offset=0,
            end_offset=18,
            context_type="text",
            context_ref="introduction",
            text_snippet="由于位于的 基 因 变 异 致 使 半 乳 糖 苷 酶 活性降低",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.FOUND
    assert grounded[0].source is not None
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
    assert grounded[0].raw_source is not None


def test_source_grounding_prefers_nearest_match_for_title_disease_diagnosis():
    text = "A case of Fabry disease\nBody text mentions Fabry disease again."
    document = TrackDocument(
        document_id="doc-en",
        track=Track.TRANSLATED,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    title_start = text.index("Fabry disease")
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="Fabry disease",
        source=SourceLocation(
            span_id="raw-title",
            page=1,
            start_offset=0,
            end_offset=20,
            context_type="text",
            context_ref="title",
            text_snippet="Fabry disease",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=1.0,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.FOUND
    assert grounded[0].source is not None
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
    assert grounded[0].source.start_offset == title_start


def test_source_grounding_falls_back_to_table_content_for_table_sources():
    document = TrackDocument(
        document_id="doc-table",
        track=Track.ORIGINAL,
        formatted_text=(
            "表1 患者酶替代疗法治疗前后实验室及心脏超声检查结果\n"
            "项目 血肌酐 eGFR 尿蛋白 肌钙蛋白I 脱乙酰基三己糖酰基鞘脂醇\n"
            "治疗前 136 49 阴性 238.8 80.23\n"
            "治疗后 141 47 阴性 204.9 33.82"
        ),
        page_spans=[PageSpan(span_id="p2", page=2, start_offset=0, end_offset=109)],
    )
    item = EvidenceItem(
        field_id="B.biochemical_markers",
        category="B",
        field_name="Biochemical markers",
        status=EvidenceStatus.FOUND,
        value="Lyso-GL-3: 80.23 ng/ml (pre), 33.82 ng/ml (post)",
        source=SourceLocation(
            span_id="table1",
            page=2,
            start_offset=0,
            end_offset=0,
            context_type="table",
            context_ref="Table 1",
            text_snippet="表1 患者酶替代疗法治疗前后实验室及心脏超声检查结果",
            block_type="table",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.FOUND
    assert grounded[0].source is not None
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
