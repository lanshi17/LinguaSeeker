from src.domain.graph.structural_variant_parser import parse_structural_variant


def _build_payload(text: str) -> dict:
	return {
		"extracted_fields": {
			"variant": {"evidence_quote": text},
			"transcript_id": {"transcript_id": "NM_000527.4"},
			"disease_chpo": {"disease_name": "Familial Hypercholesterolemia"},
		},
	}


def test_parse_structural_variant_from_variant_quote() -> None:
	text = "Case 1 harbors exons 2-10 deletion across NM_000527.4."
	result = parse_structural_variant(
		_build_payload(text),
		transcript_id="NM_000527.4",
		disease_name="Familial Hypercholesterolemia",
	)
	assert result is not None
	assert result.exon_range == "2-10"
	assert result.structural_type == "DELETION"
	assert result.synthetic_hgvs.startswith("NM_000527.4:c.(?_?)del")


def test_parse_structural_variant_from_markdown_duplication() -> None:
	payload = {
		"origin_format_md": "The proband shows exons 3 to 5 duplication (copy number gain).",
		"extracted_fields": {
			"transcript_id": {"transcript_id": "NM_000321.2"},
			"disease_chpo": {"disease_name": "Myopathy"},
		},
	}
	result = parse_structural_variant(
		payload,
		transcript_id="NM_000321.2",
		disease_name="Myopathy",
	)
	assert result is not None
	assert result.structural_type == "DUPPLICATION"
	assert result.exon_range == "3-5"
	assert "dup" in result.synthetic_hgvs


def test_parse_structural_variant_requires_transcript_and_disease() -> None:
	text = "The study reports an exon 4 deletion."
	assert (
		parse_structural_variant(
			_build_payload(text),
			transcript_id=None,
			disease_name="FH",
		)
		is None
	)
	assert (
		parse_structural_variant(
			_build_payload(text),
			transcript_id="NM_000527.4",
			disease_name=None,
		)
		is None
	)
