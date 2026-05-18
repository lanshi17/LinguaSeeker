"""Tests for the keyword-based literature type classifier."""

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
    OnlineAcquisitionItem,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.literature_type_classifier import (
    LiteratureType,
    classify_item,
    classify_items,
    filter_by_type,
)


def _make_item(title: str, journal: str = "", keywords: list[str] | None = None) -> OnlineAcquisitionItem:
    return OnlineAcquisitionItem(
        source="test",
        title=title,
        journal=journal,
        keywords=keywords or [],
    )


# --- Case report classification ---


class TestCaseReportClassification:
    def test_case_report_in_title(self):
        item = _make_item("A novel BRCA1 mutation in a patient with breast cancer: a case report")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_case_series_in_title(self):
        item = _make_item("BRCA1/2 mutations in hereditary breast cancer: a case series of 12 families")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_case_study_in_title(self):
        item = _make_item("Genomic profiling of triple-negative breast cancer: a case study")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_clinical_case_in_title(self):
        item = _make_item("Clinical case of Li-Fraumeni syndrome with novel TP53 variant")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_case_report_journal(self):
        item = _make_item("BRCA1 epimutation in breast cancer", journal="J Med Case Rep")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_bmj_case_reports_journal(self):
        item = _make_item("Novel variant in ATM gene", journal="BMJ Case Reports")
        assert classify_item(item) == LiteratureType.CASE_REPORT


# --- Sequencing classification ---


class TestSequencingClassification:
    def test_ngs_in_title(self):
        item = _make_item("BRCA1/2 mutation detection by next-generation sequencing in hereditary breast cancer")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_wgs_in_title(self):
        item = _make_item("Whole genome sequencing reveals novel structural variants in BRCA1")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_wes_in_title(self):
        item = _make_item("Whole exome sequencing identifies pathogenic variants in cancer predisposition genes")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_targeted_sequencing(self):
        item = _make_item("Targeted sequencing of 94 cancer genes in tumor samples")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_gene_panel(self):
        item = _make_item("Clinical validation of a gene panel test for hereditary cancer")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_ngs_abbreviation(self):
        item = _make_item("NGS-based variant calling in clinical oncology")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_sequencing_platform(self):
        item = _make_item("Variant detection using Illumina MiSeq in BRCA1/2 genes")
        assert classify_item(item) == LiteratureType.SEQUENCING

    def test_sanger_sequencing(self):
        item = _make_item("Confirmation of BRCA1 mutations by Sanger sequencing")
        assert classify_item(item) == LiteratureType.SEQUENCING


# --- Functional classification ---


class TestFunctionalClassification:
    def test_in_vitro(self):
        item = _make_item("Functional characterization of BRCA1 variants in vitro")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_in_vivo(self):
        item = _make_item("Tumor suppressor activity of BRCA1 in vivo using mouse models")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_knockdown(self):
        item = _make_item("BRCA1 knockdown impairs DNA damage repair in breast cancer cells")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_overexpression(self):
        item = _make_item("Overexpression of wild-type BRCA1 restores homologous recombination")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_cell_line(self):
        item = _make_item("Analysis of BRCA1 mutations in MCF-7 and HeLa cell lines")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_luciferase_assay(self):
        item = _make_item("Transcriptional activity of BRCA1 mutants measured by luciferase assay")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_western_blot(self):
        item = _make_item("BRCA1 protein expression analyzed by Western blot")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_crispr(self):
        item = _make_item("CRISPR-Cas9 editing of BRCA1 to study variant pathogenicity")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_mouse_model(self):
        item = _make_item("BRCA1-deficient mouse model reveals tumor suppressor function")
        assert classify_item(item) == LiteratureType.FUNCTIONAL

    def test_functional_assay(self):
        item = _make_item("Functional assay reveals pathogenicity of BRCA1 VUS")
        assert classify_item(item) == LiteratureType.FUNCTIONAL


# --- No classification ---


class TestNoClassification:
    def test_generic_title_returns_none(self):
        item = _make_item("Breast cancer genes BRCA1 and BRCA2")
        assert classify_item(item) is None

    def test_review_article_returns_none(self):
        item = _make_item("A review of BRCA1/2 testing in clinical practice")
        assert classify_item(item) is None


# --- Priority rules ---


class TestPriority:
    def test_case_report_takes_priority_over_sequencing(self):
        item = _make_item("BRCA1 mutation detected by NGS: a case report")
        assert classify_item(item) == LiteratureType.CASE_REPORT

    def test_sequencing_takes_priority_over_functional(self):
        item = _make_item("In vitro characterization of BRCA1 variants by next-generation sequencing")
        assert classify_item(item) == LiteratureType.SEQUENCING


# --- classify_items ---


class TestClassifyItems:
    def test_groups_by_type(self):
        items = [
            _make_item("A case report of BRCA1 mutation"),
            _make_item("NGS-based screening of cancer genes"),
            _make_item("Functional study of BRCA1 in vitro"),
            _make_item("A review of BRCA testing"),
        ]
        result = classify_items(items)
        assert len(result[LiteratureType.CASE_REPORT]) == 1
        assert len(result[LiteratureType.SEQUENCING]) == 1
        assert len(result[LiteratureType.FUNCTIONAL]) == 1

    def test_empty_input(self):
        result = classify_items([])
        assert all(len(v) == 0 for v in result.values())


# --- filter_by_type ---


class TestFilterByType:
    def test_filter_single_type(self):
        items = [
            _make_item("A case report of BRCA1 mutation"),
            _make_item("NGS-based screening of cancer genes"),
            _make_item("Functional study of BRCA1 in vitro"),
        ]
        filtered = filter_by_type(items, [LiteratureType.SEQUENCING])
        assert len(filtered) == 1
        assert "NGS" in filtered[0].title

    def test_filter_multiple_types(self):
        items = [
            _make_item("A case report of BRCA1 mutation"),
            _make_item("NGS-based screening of cancer genes"),
            _make_item("Functional study of BRCA1 in vitro"),
        ]
        filtered = filter_by_type(items, [LiteratureType.CASE_REPORT, LiteratureType.FUNCTIONAL])
        assert len(filtered) == 2

    def test_filter_excludes_unclassified(self):
        items = [
            _make_item("A review of BRCA testing"),
            _make_item("A case report of BRCA1 mutation"),
        ]
        filtered = filter_by_type(items, [LiteratureType.CASE_REPORT])
        assert len(filtered) == 1
