from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    ExtractionTarget,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.block_selection import (
    select_recall_first_blocks,
)


def _document(blocks: list[ContentBlock]) -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=blocks,
        extraction_target=ExtractionTarget(
            gene_symbol="ABCB4",
            disease_name="progressive familial intrahepatic cholestasis type 3",
        ),
    )


def test_select_recall_first_blocks_always_keeps_target_gene_and_disease_block() -> None:
    doc = _document(
        [
            ContentBlock(text="Background list of unrelated cholestasis disorders."),
            ContentBlock(
                text=(
                    "Biallelic pathogenic variants in ABCB4 cause progressive familial "
                    "intrahepatic cholestasis type 3."
                )
            ),
            ContentBlock(text="General discussion of liver disease."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=1)

    assert [block.index for block in selected] == [1]
    assert selected[0].score > 0
    assert "target_gene" in selected[0].reasons
    assert "target_disease" in selected[0].reasons


def test_select_recall_first_blocks_ranks_unrelated_disease_list_lower() -> None:
    doc = _document(
        [
            ContentBlock(
                text=(
                    "Differential diagnosis includes cystic fibrosis, Alagille syndrome, "
                    "and progressive familial intrahepatic cholestasis type 1."
                )
            ),
            ContentBlock(
                text=(
                    "The proband carried ABCB4 variants and was diagnosed with progressive "
                    "familial intrahepatic cholestasis type 3."
                )
            ),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=2)

    assert [block.index for block in selected] == [1, 0]
    assert selected[0].score > selected[1].score


def test_select_recall_first_blocks_retains_target_table_caption() -> None:
    doc = _document(
        [
            ContentBlock(text="Short abstract without the target gene."),
            ContentBlock(
                type="table",
                table_caption=["Table 2. ABCB4 variants in PFIC3 families"],
                table_body="c.959C>T pathogenic variant; progressive familial intrahepatic cholestasis type 3",
            ),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=1)

    assert [block.index for block in selected] == [1]
    assert "table_or_caption" in selected[0].reasons
    assert "target_gene" in selected[0].reasons


def test_select_recall_first_blocks_ignores_empty_blocks() -> None:
    doc = _document(
        [
            ContentBlock(text=""),
            ContentBlock(table_caption=[""], table_body=""),
            ContentBlock(text="ABCB4 causes progressive familial intrahepatic cholestasis type 3."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=5)

    assert [block.index for block in selected] == [2]


def test_select_recall_first_blocks_includes_neighbor_context_when_budget_allows() -> None:
    doc = _document(
        [
            ContentBlock(text="The proband had neonatal cholestasis and elevated GGT."),
            ContentBlock(
                text=(
                    "Biallelic pathogenic ABCB4 changes cause progressive familial "
                    "intrahepatic cholestasis type 3."
                )
            ),
            ContentBlock(text="Segregation analysis confirmed both parents were carriers."),
            ContentBlock(text="Unrelated references and acknowledgements."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=3)

    assert [block.index for block in selected] == [1, 0, 2]
    assert selected[1].reasons == ("target_neighbor",)
    assert selected[2].reasons == ("target_neighbor",)


def test_select_recall_first_blocks_neighbor_expansion_respects_max_blocks() -> None:
    doc = _document(
        [
            ContentBlock(text="The proband had neonatal cholestasis and elevated GGT."),
            ContentBlock(
                text=(
                    "Biallelic pathogenic ABCB4 changes cause progressive familial "
                    "intrahepatic cholestasis type 3."
                )
            ),
            ContentBlock(text="Segregation analysis confirmed both parents were carriers."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=2)

    assert len(selected) == 2
    assert [block.index for block in selected] == [1, 0]


def test_select_recall_first_blocks_prefers_target_neighbor_over_unrelated_scored_block() -> None:
    doc = _document(
        [
            ContentBlock(text="The proband had neonatal cholestasis and elevated GGT."),
            ContentBlock(
                text=(
                    "Biallelic pathogenic ABCB4 changes cause progressive familial "
                    "intrahepatic cholestasis type 3."
                )
            ),
            ContentBlock(text="An unrelated BRCA1 variant was discussed in the methods."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=2)

    assert [block.index for block in selected] == [1, 0]


def test_select_recall_first_blocks_keeps_target_disease_block_ahead_of_neighbor() -> None:
    doc = _document(
        [
            ContentBlock(text="The proband had neonatal cholestasis and elevated GGT."),
            ContentBlock(text="Biallelic pathogenic ABCB4 changes were identified."),
            ContentBlock(text="progressive familial intrahepatic cholestasis type 3 was diagnosed."),
            ContentBlock(text="An unrelated BRCA1 variant was discussed in the methods."),
        ]
    )

    selected = select_recall_first_blocks(doc, max_blocks=2)

    assert [block.index for block in selected] == [1, 2]
