from src.core.evidence_extraction.contracts import (
    ContentBlock,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.core import SourceGrounder


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
        raw_source=SourceLocation(
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
    assert grounded[0].raw_source is not None


def test_source_grounding_corrects_wrong_offset():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS cDNA",
        status=EvidenceStatus.FOUND,
        value="c.68_69delAG",
        raw_source=SourceLocation(
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
        raw_source=SourceLocation(
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


def test_source_grounding_recovers_protein_hgvs_missing_p_prefix():
    text = "A homozygous missense mutation, Thr240Met, was found in exon 6."
    document = TrackDocument(
        document_id="doc-hgvs-alias",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value="p.Thr240Met",
        raw_source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=len("p.Thr240Met"),
            context_type="text",
            context_ref="Results",
            text_snippet="p.Thr240Met",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert grounded.source.text_snippet == "Thr240Met"


def test_source_grounding_recovers_protein_hgvs_compound_parenthesis_spacing():
    text = "The report lists p.R267fs*6(p.Arg267fsTer6) in MECP2."
    document = TrackDocument(
        document_id="doc-hgvs-compound",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value="p.R267fs*6 (p.Arg267fsTer6)",
        raw_source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=len("p.R267fs*6 (p.Arg267fsTer6)"),
            context_type="text",
            context_ref="Results",
            text_snippet="p.R267fs*6 (p.Arg267fsTer6)",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert grounded.source.text_snippet == "p.R267fs*6(p.Arg267fsTer6)"


def test_source_grounding_marks_missing_image_source_as_ocr_gap():
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value="p.R227X",
        raw_source=SourceLocation(
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


def test_source_grounding_marks_ellipsis_snippet_as_invalid():
    document = TrackDocument(
        document_id="doc-ellipsis",
        track=Track.ORIGINAL,
        formatted_text="This is a pathogenic mutation and the most common mutation leading to classic phenotype.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=88)],
    )
    item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="p.R227X is a known pathogenic mutation",
        raw_source=SourceLocation(
            span_id="raw-ellipsis",
            page=1,
            start_offset=0,
            end_offset=56,
            context_type="text",
            context_ref="discussion",
            text_snippet="This is a pathogenic mutation... the most common mutation",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.8,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.SOURCE_INVALID
    assert grounded[0].raw_source is not None


def test_source_grounding_marks_table_miss_as_table_ungrounded():
    document = TrackDocument(
        document_id="doc-table-miss",
        track=Track.ORIGINAL,
        formatted_text="Table 1 laboratory results are not fully text-extracted here.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=61)],
    )
    item = EvidenceItem(
        field_id="B.biochemical_markers",
        category="B",
        field_name="Biochemical markers",
        status=EvidenceStatus.FOUND,
        value="Lyso-GL-3 80.23 ng/mL",
        raw_source=SourceLocation(
            span_id="table-1",
            page=1,
            start_offset=0,
            end_offset=0,
            context_type="table",
            context_ref="Table 1",
            text_snippet="治疗前 136 49 阴性 238.8 80.23",
            block_type="table",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.8,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.TABLE_UNGROUNDED


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
        raw_source=SourceLocation(
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


def test_source_grounding_normalizes_fullwidth_to_halfwidth_punctuation():
    """A snippet using halfwidth parens must match a document using fullwidth
    parens (and vice versa) via the normalized search path, not go SOURCE_INVALID."""
    document = TrackDocument(
        document_id="doc-fw",
        track=Track.ORIGINAL,
        formatted_text="患儿父母均未检测到突变（结果见图1）。",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=22)],
    )
    item = EvidenceItem(
        field_id="A.gene_disease_relationship",
        category="A",
        field_name="Gene disease relationship",
        status=EvidenceStatus.FOUND,
        value="父母未检测到突变",
        raw_source=SourceLocation(
            span_id="raw-1",
            page=1,
            start_offset=0,
            end_offset=15,
            context_type="text",
            context_ref="results",
            # Snippet uses HALFWIDTH parens; document uses FULLWIDTH.
            text_snippet="父母均未检测到突变(结果见图1)",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.FOUND
    assert grounded[0].source is not None
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED


def test_source_grounding_normalizes_case_difference():
    """A snippet whose only difference from the document is letter case must
    match via the normalized search path, not go SOURCE_INVALID."""
    document = TrackDocument(
        document_id="doc-case",
        track=Track.TRANSLATED,
        formatted_text="The MECP2 gene is causative for Rett syndrome.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=46)],
    )
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="MECP2",
        raw_source=SourceLocation(
            span_id="raw-1",
            page=1,
            start_offset=0,
            end_offset=10,
            context_type="text",
            context_ref="introduction",
            text_snippet="mecp2 gene is causative",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])

    assert grounded[0].status == EvidenceStatus.FOUND
    assert grounded[0].source is not None
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED


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
        raw_source=SourceLocation(
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
    assert grounded[0].source.source_precision == SourcePrecision.AMBIGUOUS
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
        raw_source=SourceLocation(
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


def _doc_with_blocks() -> TrackDocument:
    text = "Intro\nBRCA1 c.5266dupC\nFigure caption loss of function"
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Intro", bbox=[0, 0, 10, 10]),
            ContentBlock(type="table", page_idx=0, table_body="BRCA1 c.5266dupC", bbox=[10, 10, 20, 20]),
            ContentBlock(type="chart", page_idx=0, content="Figure caption loss of function", bbox=[20, 20, 30, 30]),
        ],
    )


def test_grounder_uses_block_bbox_and_type():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=1, context_type="table", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc_with_blocks(), [item])[0]

    assert grounded.source is not None
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]
    assert grounded.source.block_type == "table"


def test_grounder_corrects_wrong_llm_block_index_from_text_match():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc_with_blocks(), [item])[0]

    assert grounded.raw_source.block_index == 0
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]


def test_grounder_falls_back_to_pure_text_without_blocks():
    text = "BRCA1 c.5266dupC"
    doc = TrackDocument(
        document_id="old-doc",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.source.start_offset >= 0
    assert grounded.source.block_index == -1


def test_grounder_keeps_table_caption_hit_as_found():
    text = "Table 1. Variants"
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="table", page_idx=0, table_caption=["Table 1. Variants"], bbox=[1, 2, 3, 4])],
    )
    item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="Table 1",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=0, context_type="table", context_ref="Table 1. Variants", text_snippet="Table 1. Variants"
        ),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source.block_type == "table"


def test_grounder_marks_image_miss_as_ocr_gap():
    doc = _doc_with_blocks()
    item = EvidenceItem(
        field_id="F.functional_result",
        category="F",
        field_name="Functional result",
        status=EvidenceStatus.FOUND,
        value="missing gel band",
        confidence=0.7,
        raw_source=SourceLocation(
            block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="missing gel band"
        ),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.OCR_GAP


def test_grounder_preserves_special_record_on_failure_with_no_source():
    doc = _doc_with_blocks()
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Missing figure evidence",
        raw_source=SourceLocation(
            block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="not present"
        ),
        group_id="gene=BRCA1|variant=c.5266dupC",
    )

    grounded = SourceGrounder().ground_special_records(doc, [record])[0]

    assert grounded.source is None
    assert grounded.raw_source is not None


def test_grounder_grounds_caption_text_not_present_in_formatted_text():
    text = "BRCA1 c.5266dupC"
    doc = TrackDocument(
        document_id="doc-caption",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[
            ContentBlock(
                type="table",
                page_idx=0,
                table_body="BRCA1 c.5266dupC",
                table_caption=["Table 1. Variants"],
                bbox=[5, 6, 7, 8],
            )
        ],
    )
    item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="Table 1",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=0,
            context_type="table",
            context_ref="Table 1. Variants",
            text_snippet="Table 1. Variants",
        ),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert grounded.source.block_index == 0
    assert grounded.source.bbox == [5, 6, 7, 8]
    assert grounded.source.text_snippet == "Table 1. Variants"


def test_grounder_uses_matched_block_for_duplicate_snippet_provenance():
    text = "BRCA1\nBRCA1"
    doc = TrackDocument(
        document_id="doc-dup",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="BRCA1", bbox=[1, 1, 2, 2]),
            ContentBlock(type="text", page_idx=0, text="BRCA1", bbox=[9, 9, 10, 10]),
        ],
    )
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=1,
            context_type="text",
            context_ref="",
            text_snippet="BRCA1",
        ),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.source is not None
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [9, 9, 10, 10]


def test_source_grounding_matches_decoded_hgvs_quote_to_html_entity() -> None:
    """MinerU/HTML leaves c.538C&gt;T; the model copies c.538C>T. Keep FOUND."""
    text = "Sanger证实为杂合突变c.538C&gt;T（p.Arg180Ter）。"
    document = TrackDocument(
        document_id="rett-007-html-hgvs",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.538C>T",
        raw_source=SourceLocation(
            context_type="text",
            context_ref="primary_broad_extraction",
            text_snippet="c.538C>T",
            block_index=-1,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert "c.538C" in grounded.source.text_snippet
    assert grounded.source.text_snippet in text


def test_source_grounding_matches_html_entity_inside_chinese_sentence() -> None:
    """A decoded quote spanning Chinese context still grounds when only '>' is an entity."""
    text = "病例2存在MECP2基因突变c.538C&gt;T，患儿父母均未检测到突变。"
    document = TrackDocument(
        document_id="rett-007-html-sentence",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    item = EvidenceItem(
        field_id="C.de_novo_status",
        category="C",
        field_name="De novo status",
        status=EvidenceStatus.FOUND,
        value="de_novo",
        raw_source=SourceLocation(
            context_type="text",
            context_ref="primary_broad_extraction",
            text_snippet="MECP2基因突变c.538C>T，患儿父母均未检测到突变",
            block_index=-1,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert "父母均未检测到突变" in grounded.source.text_snippet


def test_source_grounding_falls_back_to_hgvs_value_when_quote_is_paraphrased() -> None:
    """If the quote is not verbatim, a coding HGVS value that appears in the paper still grounds."""
    text = "该先证者携带c.538C&gt;T。"
    document = TrackDocument(
        document_id="rett-007-value-fallback",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.538C>T",
        raw_source=SourceLocation(
            context_type="text",
            context_ref="primary_broad_extraction",
            text_snippet="the heterozygous coding variant was confirmed by Sanger",
            block_index=-1,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(document, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source is not None
    assert grounded.source.text_snippet in text
