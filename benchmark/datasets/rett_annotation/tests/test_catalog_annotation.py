"""Tests for catalog-driven Rett annotation helpers."""
from __future__ import annotations

import unittest

from src.catalog_annotation import (
    build_evaluation_config,
    build_expected_json,
    evaluation_type_for_field,
    load_literature_catalog,
)


class CatalogAnnotationTest(unittest.TestCase):
    def test_loads_current_literature_catalog_without_curation_fields(self) -> None:
        fields = load_literature_catalog()
        field_ids = [field.field_id for field in fields]

        self.assertEqual(143, len(fields))
        self.assertIn("A.gene_aliases", field_ids)
        self.assertIn("F.functional_result", field_ids)
        self.assertIn("J.reputable_benign_assertion", field_ids)
        self.assertNotIn("K.mode_of_inheritance", field_ids)

    def test_build_expected_json_keeps_only_non_empty_catalog_values(self) -> None:
        fields = load_literature_catalog()
        parsed = {
            "metadata": {
                "gene_symbol": "MECP2",
                "disease_diagnosis": "Rett syndrome",
                "mode_of_inheritance": "XD",
                "source_title": "Example Rett article",
                "source_year": "2026",
            },
            "variants": [
                {
                    "hgvs_c": "c.808C>T",
                    "hgvs_p": "p.R270X",
                    "variant_type": "nonsense",
                }
            ],
            "field_values": {
                "A.gene_symbol": "MECP2",
                "A.variant_hgvs_c": ["c.808C>T", ""],
                "B.hpo_terms": ["HP:0001250", "HP:0002072"],
                "F.functional_result": "reduced transcriptional repression",
                "K.mode_of_inheritance": "XL",
                "B.case_count": "",
            },
        }

        expected = build_expected_json(
            entry_id="rett_test",
            language="en",
            parsed=parsed,
            fields=fields,
        )
        evidence_by_id = {item.field_id: item for item in expected.expected_evidence}

        self.assertEqual("Example Rett article", expected.source_title)
        self.assertEqual("Rett syndrome", expected.disease_label)
        self.assertEqual("XD", expected.moi)
        self.assertEqual("c.808C>T", expected.variants[0].hgvs_c)
        self.assertIn("A.gene_symbol", evidence_by_id)
        self.assertEqual("c.808C>T", evidence_by_id["A.variant_hgvs_c"].value)
        self.assertEqual(["c.808C>T"], evidence_by_id["A.variant_hgvs_c"].candidates)
        self.assertEqual("HP:0001250; HP:0002072", evidence_by_id["B.hpo_terms"].value)
        self.assertEqual("reduced transcriptional repression", evidence_by_id["F.functional_result"].value)
        self.assertNotIn("K.mode_of_inheritance", evidence_by_id)
        self.assertNotIn("B.case_count", evidence_by_id)

    def test_evaluation_config_matches_catalog_groups(self) -> None:
        fields = load_literature_catalog()
        config = build_evaluation_config(fields)
        evidence_ids = [
            field_id
            for group, values in config.items()
            if group != "standardization_fields"
            for field_id in values
        ]
        field_ids = {field.field_id for field in fields}

        self.assertEqual(field_ids, set(evidence_ids))
        self.assertIn("F.functional_result", config["functional_fields"])
        self.assertIn("H.contradiction_type", config["contradiction_fields"])
        self.assertIn("J.reputable_benign_assertion", config["authority_fields"])
        self.assertTrue(all(not field_id.startswith("K.") for field_id in evidence_ids))

    def test_variant_fields_are_precision_only(self) -> None:
        self.assertEqual("precision_only", evaluation_type_for_field("A.variant_hgvs_p"))
        self.assertEqual("precision_only", evaluation_type_for_field("A.same_residue_other_missense"))
        self.assertEqual("precision_recall", evaluation_type_for_field("B.disease_diagnosis"))


if __name__ == "__main__":
    unittest.main()
