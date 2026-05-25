"""Tests for Phase 3 terminology import parsers."""
from __future__ import annotations

from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.importers import (
    _clinvar_review_stars,
    _collect_alias_values,
    _iter_tsv_rows,
    _normalize_rsid,
    _split_comma_values,
    is_importable_clinvar_review_status,
    parse_clingen_rows,
    parse_clinvar_rows,
    parse_hgnc_rows,
    parse_hpo_rows,
    parse_omim_rows,
)


def test_parse_hgnc_rows_builds_gene_entry_and_aliases(tmp_path: Path) -> None:
    """HGNC rows produce a gene entry plus queryable aliases."""
    path = tmp_path / "hgnc_complete_set.txt"
    path.write_text(
        "HGNC ID\tApproved symbol\tApproved name\tAlias symbols\tPrevious symbols\n"
        "1100\tBRCA1\tBRCA1 DNA repair associated\tRNF53, BRCC1\tFANCS\n",
        encoding="utf-8",
    )

    batch = parse_hgnc_rows(path, version="hgnc_test")

    assert batch.entries[0].external_id == "HGNC:1100"
    assert batch.entries[0].display_name == "BRCA1"
    assert {alias.alias_text for alias in batch.aliases} >= {"BRCA1", "RNF53", "BRCC1", "FANCS"}


def test_clinvar_review_status_filters_zero_star() -> None:
    """ClinVar import excludes review statuses that encode 0-star evidence."""
    assert is_importable_clinvar_review_status("criteria provided, single submitter")
    assert is_importable_clinvar_review_status("criteria provided, conflicting classifications")
    assert not is_importable_clinvar_review_status("no assertion criteria provided")
    assert not is_importable_clinvar_review_status("no classification provided")


def test_parse_omim_rows_builds_disease_entries(tmp_path: Path) -> None:
    """OMIM title rows create OMIM-prefixed disease entries."""
    root = tmp_path / "omim"
    root.mkdir()
    (root / "mimTitles.txt").write_text(
        "# Prefix\tMIM Number\tPreferred Title; symbol\n"
        "*\t100100\tExample disease\n",
        encoding="utf-8",
    )

    batch = parse_omim_rows(root, version="omim_test")

    assert batch.entries[0].external_id == "OMIM:100100"
    assert batch.entries[0].display_name == "Example disease"


def test_parse_hpo_rows_builds_phenotype_entries(tmp_path: Path) -> None:
    """HPO JSON rows create HP-prefixed phenotype entries."""
    root = tmp_path / "hpo"
    root.mkdir()
    (root / "hp.json").write_text(
        '{"graphs":[{"nodes":[{"id":"http://purl.obolibrary.org/obo/HP_0001250","lbl":"Seizure"}]}]}',
        encoding="utf-8",
    )

    batch = parse_hpo_rows(root, version="hpo_test")

    assert batch.entries[0].external_id == "HP:0001250"
    assert batch.entries[0].display_name == "Seizure"


def test_parse_clingen_rows_builds_mondo_entries_and_relationships(tmp_path: Path) -> None:
    """ClinGen disease summaries create MONDO fallback entries and gene relationships."""
    root = tmp_path / "clingen"
    root.mkdir()
    (root / "Clingen-Gene-Disease-Summary.csv").write_text(
        "GENE SYMBOL,DISEASE LABEL,DISEASE ID,CLASSIFICATION\n"
        "BRCA2,Breast cancer,MONDO:0012934,Definitive\n",
        encoding="utf-8",
    )
    (root / "Clingen-Dosage-Sensitivity.csv").write_text(
        "Gene Symbol,Dosage Sensitivity Map,Score\n",
        encoding="utf-8",
    )

    batch = parse_clingen_rows(root, version="clingen_test")

    assert any(entry.external_id == "MONDO:0012934" for entry in batch.entries)
    relationship = batch.relationships[0]
    assert relationship.relationship_type == "gene_associated_with_disease"
    assert relationship.object_external_id == "MONDO:0012934"


def test_parse_clinvar_rows_keeps_significance_as_scalar_relationship(tmp_path: Path) -> None:
    """ClinVar rows create variant entries, rsID aliases, and scalar significance relationships."""
    path = tmp_path / "variant_summary.txt"
    path.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsingle nucleotide variant\tNM_000059.4(BRCA2):c.5946del\t675\tBRCA2\tHGNC:1101\tPathogenic\t1\t2024-01-01\t80359550\t"
        "-\tRCV0001\tOMIM:612555\tBreast cancer\tgermline\tgermline\tGRCh38\tNC_000013.11\t13\t1\t1\tA\t-\t-\t"
        "criteria provided, single submitter\t1\t-\tN\t-\t-\t12345\n",
        encoding="utf-8",
    )

    batch = parse_clinvar_rows(path, version="clinvar_test")

    assert batch.entries[0].external_id == "ClinVarVariation:12345"
    assert any(alias.alias_text == "rs80359550" for alias in batch.aliases)
    relationship = batch.relationships[0]
    assert relationship.relationship_type == "variant_has_clinical_significance"
    assert relationship.object_external_id is None
    assert relationship.raw_payload["clinical_significance"] == "Pathogenic"


def test_collect_alias_values_deduplicates_and_preserves_first_seen_order() -> None:
    """Alias payload collection keeps first-seen order while removing duplicates."""
    assert _collect_alias_values("BRCA1", " RNF53, BRCA1 ", "FANCS, RNF53") == [
        "BRCA1",
        "RNF53",
        "FANCS",
    ]


def test_split_comma_values_handles_none_and_whitespace() -> None:
    """Comma splitting ignores empty fragments and trims each alias."""
    assert _split_comma_values(None) == []
    assert _split_comma_values(" BRCA1, , RNF53 ,, FANCS ") == ["BRCA1", "RNF53", "FANCS"]


def test_iter_tsv_rows_strips_hash_prefixed_header_and_handles_empty_file(tmp_path: Path) -> None:
    """TSV iteration treats hash-prefixed headers as real headers and streams no rows for empties."""
    path = tmp_path / "sample.tsv"
    path.write_text("#ColumnA\tColumnB\nleft\tright\n", encoding="utf-8")

    rows = list(_iter_tsv_rows(path))

    assert rows == [{"ColumnA": "left", "ColumnB": "right"}]
    empty = tmp_path / "empty.tsv"
    empty.write_text("", encoding="utf-8")
    assert list(_iter_tsv_rows(empty)) == []


def test_normalize_rsid_handles_missing_prefixed_and_bare_values() -> None:
    """rsID normalization accepts absent, pre-prefixed, and numeric forms."""
    assert _normalize_rsid(None) is None
    assert _normalize_rsid("-") is None
    assert _normalize_rsid("rs80359550") == "rs80359550"
    assert _normalize_rsid("80359550") == "rs80359550"


def test_clinvar_review_stars_maps_all_documented_levels() -> None:
    """Review status mapping preserves the documented star-level buckets."""
    assert _clinvar_review_stars("practice guideline") == "4_star"
    assert _clinvar_review_stars("reviewed by expert panel") == "3_star"
    assert _clinvar_review_stars("criteria provided, multiple submitters, no conflicts") == "2_star"
    assert _clinvar_review_stars("criteria provided, single submitter") == "1_star"
    assert _clinvar_review_stars("") is None


def test_parse_hpo_rows_obo_path_skips_obsolete_terms(tmp_path: Path) -> None:
    """HPO OBO parsing excludes obsolete terms and keeps active phenotype entries."""
    root = tmp_path / "hpo_obo"
    root.mkdir()
    (root / "hp.obo").write_text(
        "[Term]\n"
        "id: HP:0000118\n"
        "name: Phenotypic abnormality\n"
        "\n"
        "[Term]\n"
        "id: HP:9999999\n"
        "name: Obsolete phenotype\n"
        "is_obsolete: true\n",
        encoding="utf-8",
    )

    batch = parse_hpo_rows(root, version="hpo_obo_test")

    assert [entry.external_id for entry in batch.entries] == ["HP:0000118"]


def test_parse_hpo_rows_obo_flushes_on_new_non_term_stanza(tmp_path: Path) -> None:
    """HPO OBO parsing finalizes a term before entering a non-Term stanza like Typedef."""
    root = tmp_path / "hpo_typedef"
    root.mkdir()
    (root / "hp.obo").write_text(
        "[Term]\n"
        "id: HP:0000001\n"
        "name: Term one\n"
        "\n"
        "[Typedef]\n"
        "id: part_of\n"
        "name: part of\n",
        encoding="utf-8",
    )

    batch = parse_hpo_rows(root, version="hpo_typedef_test")

    assert [(entry.external_id, entry.display_name) for entry in batch.entries] == [
        ("HP:0000001", "Term one"),
    ]
