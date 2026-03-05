from src.utils.evidence_annotation import enrich_evidence_json


def test_enrich_evidence_json_adds_positions_and_extractions() -> None:
    en_text = (
        "BRCA1 c.123A>G in breast cancer was tested by luciferase assay and "
        "showed reduced activity."
    )

    payload = {
        "evidence_annotations": [
            {
                "id": "E1",
                "type": "text",
                "quote": "BRCA1 c.123A>G in breast cancer",
                "keywords": {"raw": ["BRCA1", "c.123A>G", "breast cancer"]},
            }
        ],
        "extracted_fields": {
            "gene": {"symbol": "BRCA1"},
            "variant": {"hgvs_c": "c.123A>G"},
            "disease_chpo": {"disease_name": "breast cancer"},
            "experiment_data": {
                "assay_type": "luciferase assay",
                "method_description": "luciferase assay",
                "key_findings": ["reduced activity"],
            },
        },
        "overall_assessment": {"final_recommendation": "approved"},
        "ps3_step_4": {"final_evidence_strength": "PS3_supporting"},
    }

    enriched = enrich_evidence_json(payload, en_text)

    annotation_locator = enriched["evidence_annotations"][0]["locator"]
    assert annotation_locator["start"] is not None
    assert annotation_locator["end"] is not None
    assert annotation_locator["start"] == annotation_locator["char_start"]
    assert annotation_locator["end"] == annotation_locator["char_end"]

    entities = enriched["entity_extractions"]
    assert any(
        entity["type"] == "gene" and entity["locator"]["start"] is not None for entity in entities
    )
    assert any(
        entity["type"] == "variant" and entity["locator"]["start"] is not None
        for entity in entities
    )

    relation_types = {relation["type"] for relation in enriched["relation_extractions"]}
    assert "gene_variant" in relation_types
    assert "variant_disease" in relation_types

    experiment_items = enriched["experiment_info_extractions"]
    assert any(item["category"] == "method" for item in experiment_items)
    assert any(item["category"] == "result" for item in experiment_items)


def test_enrich_evidence_json_resolves_overlap_by_longer_span() -> None:
    en_text = "BRCA1 mutation identified in sample."
    payload = {
        "evidence_annotations": [
            {
                "id": "E1",
                "type": "text",
                "quote": "BRCA1 mutation identified",
                "keywords": {"raw": ["BRCA1", "BRCA"]},
            }
        ],
        "entity_extractions": [
            {"type": "gene", "text": "BRCA", "evidence_ref": "E1"},
            {"type": "gene", "text": "BRCA1", "evidence_ref": "E1"},
        ],
    }

    enriched = enrich_evidence_json(payload, en_text)
    entity_texts = [entity["text"] for entity in enriched["entity_extractions"]]
    assert "BRCA1" in entity_texts
    assert "BRCA" not in entity_texts
