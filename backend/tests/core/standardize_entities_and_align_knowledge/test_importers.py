"""Tests for Phase 3 terminology import parsers."""
from __future__ import annotations

from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.importers import (
    _clinvar_review_stars,
    _collect_alias_values,
    _iter_tsv_rows,
    _normalize_rsid,
    _split_comma_values,
    build_clinvar_core_tsv,
    iter_clinvar_batches,
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


def test_parse_omim_rows_skips_preface_comments_before_header(tmp_path: Path) -> None:
    """Real OMIM exports may include preface comment lines before the tabular header."""
    root = tmp_path / "omim"
    root.mkdir()
    (root / "mimTitles.txt").write_text(
        "# Copyright\n"
        "# Generated: 2026-05-26\n"
        "# Prefix\tMIM Number\tPreferred Title; symbol\n"
        "NULL\t100100\tExample disease\n",
        encoding="utf-8",
    )

    batch = parse_omim_rows(root, version="omim_test")

    assert batch.entries[0].external_id == "OMIM:100100"
    assert batch.entries[0].display_name == "Example disease"


def test_parse_clingen_rows_skips_preamble_before_csv_header(tmp_path: Path) -> None:
    """Real ClinGen exports may include several prose rows before the actual CSV header."""
    root = tmp_path / "clingen"
    root.mkdir()
    (root / "Clingen-Gene-Disease-Summary.csv").write_text(
        "\"CLINGEN GENE DISEASE VALIDITY CURATIONS\",\"\"\n"
        "\"FILE CREATED: 2026-05-25\",\"\"\n"
        "\"GENE SYMBOL\",\"GENE ID (HGNC)\",\"DISEASE LABEL\",\"DISEASE ID (MONDO)\",\"CLASSIFICATION\"\n"
        "\"BRCA2\",\"1101\",\"Breast cancer\",\"MONDO:0012934\",\"Definitive\"\n",
        encoding="utf-8",
    )
    (root / "Clingen-Dosage-Sensitivity.csv").write_text(
        "\"CLINGEN DOSAGE SENSITIVITY CURATIONS\",\"\"\n"
        "\"FILE CREATED: 2026-05-25\",\"\"\n"
        "\"GENE SYMBOL\",\"HGNC ID\",\"HAPLOINSUFFICIENCY\",\"TRIPLOSENSITIVITY\",\"ONLINE REPORT\",\"DATE\"\n"
        "\"GLA\",\"4296\",\"3\",\"0\",\"https://example.test\",\"2026-05-25\"\n",
        encoding="utf-8",
    )

    batch = parse_clingen_rows(root, version="clingen_test")

    assert any(entry.external_id == "MONDO:0012934" for entry in batch.entries)
    assert any(relationship.relationship_type == "gene_has_dosage_sensitivity" for relationship in batch.relationships)


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


def test_parse_clinvar_rows_adds_one_letter_protein_alias_when_name_contains_hgvs_p(tmp_path: Path) -> None:
    """ClinVar protein names should generate a short one-letter HGVS alias for exact variant matching."""
    path = tmp_path / "variant_summary.txt"
    path.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsingle nucleotide variant\tNM_000169.3(GLA):c.679C>T (p.Arg227Ter)\t2717\tGLA\tHGNC:4296\tPathogenic\t1\t2024-01-01\t104894841\t"
        "-\tRCV0001\tOMIM:301500\tFabry disease\tgermline\tgermline\tGRCh38\tNC_000023.11\tX\t1\t1\tC\tT\t-\t"
        "criteria provided, multiple submitters, no conflicts\t1\t-\tN\t-\t-\t10733\n",
        encoding="utf-8",
    )

    batch = parse_clinvar_rows(path, version="clinvar_test")

    alias_texts = {alias.alias_text for alias in batch.aliases}
    assert "p.R227X" in alias_texts


def test_iter_clinvar_batches_yields_chunked_batches(tmp_path: Path) -> None:
    """ClinVar streaming yields bounded-size batches instead of one monolithic payload."""
    path = tmp_path / "variant_summary.txt"
    path.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsingle nucleotide variant\tNM_000059.4(BRCA2):c.5946del\t675\tBRCA2\tHGNC:1101\tPathogenic\t1\t2024-01-01\t80359550\t"
        "-\tRCV0001\tOMIM:612555\tBreast cancer\tgermline\tgermline\tGRCh38\tNC_000013.11\t13\t1\t1\tA\t-\t-\t"
        "criteria provided, single submitter\t1\t-\tN\t-\t-\t12345\n"
        "2\tsingle nucleotide variant\tNM_000059.4(BRCA2):c.7008-2A>T\t675\tBRCA2\tHGNC:1101\tLikely pathogenic\t1\t2024-01-01\t80359551\t"
        "-\tRCV0002\tOMIM:612555\tBreast cancer\tgermline\tgermline\tGRCh38\tNC_000013.11\t13\t2\t2\tA\t-\t-\t"
        "criteria provided, single submitter\t1\t-\tN\t-\t-\t12346\n",
        encoding="utf-8",
    )

    batches = list(iter_clinvar_batches(path, version="clinvar_test", chunk_size=1))

    assert len(batches) == 2
    assert [batch.entries[0].external_id for batch in batches] == [
        "ClinVarVariation:12345",
        "ClinVarVariation:12346",
    ]
    assert all(len(batch.entries) == 1 for batch in batches)


def test_build_clinvar_core_tsv_keeps_only_requested_fields(tmp_path: Path) -> None:
    """ClinVar pre-processing writes a reduced TSV containing only core alignment fields."""
    source = tmp_path / "variant_summary.txt"
    target = tmp_path / "variant_summary.core.tsv"
    source.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsingle nucleotide variant\tNM_000059.4(BRCA2):c.5946del\t675\tBRCA2\tHGNC:1101\tPathogenic\t1\t2024-01-01\t80359550\t"
        "-\tRCV0001\tOMIM:612555\tBreast cancer\tgermline\tgermline\tGRCh38\tNC_000013.11\t13\t1\t1\tA\t-\t-\t"
        "criteria provided, single submitter\t1\t-\tN\t-\t-\t12345\n",
        encoding="utf-8",
    )

    rows_written = build_clinvar_core_tsv(source, target)

    assert rows_written == 1
    written = target.read_text(encoding="utf-8").splitlines()
    assert written[0] == "\t".join([
        "VariationID",
        "Name",
        "GeneSymbol",
        "ClinicalSignificance",
        "ReviewStatus",
        "RS# (dbSNP)",
        "PhenotypeIDS",
    ])
    assert written[1] == "\t".join([
        "12345",
        "NM_000059.4(BRCA2):c.5946del",
        "BRCA2",
        "Pathogenic",
        "criteria provided, single submitter",
        "80359550",
        "OMIM:612555",
    ])


def test_build_clinvar_core_tsv_filters_zero_star_rows_and_contiguous_duplicates(tmp_path: Path) -> None:
    """ClinVar pre-processing should keep only importable rows and collapse exact contiguous duplicates."""
    source = tmp_path / "variant_summary.txt"
    target = tmp_path / "variant_summary.core.tsv"
    source.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsnv\tVariant A\t1\tGENE1\tHGNC:1\tPathogenic\t1\t2024-01-01\t101\t-\tRCV1\tOMIM:1\tPhenotype A\t-\t-\tGRCh38\t-\t1\t1\t1\tA\tT\t-\tcriteria provided, single submitter\t1\t-\tN\t-\t-\t100\n"
        "1\tsnv\tVariant A\t1\tGENE1\tHGNC:1\tPathogenic\t1\t2024-01-01\t101\t-\tRCV1\tOMIM:1\tPhenotype A\t-\t-\tGRCh38\t-\t1\t1\t1\tA\tT\t-\tcriteria provided, single submitter\t1\t-\tN\t-\t-\t100\n"
        "2\tsnv\tVariant B\t2\tGENE2\tHGNC:2\tLikely benign\t1\t2024-01-01\t102\t-\tRCV2\tOMIM:2\tPhenotype B\t-\t-\tGRCh38\t-\t1\t1\t1\tA\tT\t-\tno assertion criteria provided\t1\t-\tN\t-\t-\t200\n"
        "3\tsnv\tVariant C\t3\tGENE3\tHGNC:3\tPathogenic\t1\t2024-01-01\t103\t-\tRCV3\tOMIM:3\tPhenotype C\t-\t-\tGRCh38\t-\t1\t1\t1\tA\tT\t-\treviewed by expert panel\t1\t-\tN\t-\t-\t300\n",
        encoding="utf-8",
    )

    rows_written = build_clinvar_core_tsv(source, target)

    assert rows_written == 2
    written = target.read_text(encoding="utf-8").splitlines()
    assert len(written) == 3
    assert written[1].startswith("100\tVariant A\tGENE1\tPathogenic")
    assert written[2].startswith("300\tVariant C\tGENE3\tPathogenic")


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
